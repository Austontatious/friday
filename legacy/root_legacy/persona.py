import os
import logging
import difflib
from typing import Dict, Any, Optional
from .model_config import ModelType, model_config
from .error_handler import ModelLoadError, ModelInferenceError
from .prompt_templates import PromptTemplates
from .response_formatter import ResponseFormatter
from .model_loader_core import initialize_model_loader
from friday.tools.init_tools import *
from friday.tools.registry import list_tools
from tokenizers import Tokenizer
from transformers import PreTrainedTokenizerFast
import torch
import torch.nn.functional as F
from scipy.spatial.distance import cosine

logger = logging.getLogger("persona")

MAX_CONTEXT_LENGTH = 8192
SAFE_MARGIN = 128

class PersonaManager:
    def __init__(self, memory_manager: Optional[Any] = None):
        self.models: Dict[ModelType, Any] = {}
        self.configs: Dict[ModelType, Any] = {}
        self.current_model: ModelType = ModelType.FRIDAY
        self.memory_manager = memory_manager
        self.system_prompt = PromptTemplates.get_system_prompt(self.current_model)

    def load_model(self, model_type: ModelType) -> None:
        loader = initialize_model_loader()
        model = loader.get(model_type)

        if not model:
            raise ModelLoadError(model_type.value, "Model not loaded")

        config = model_config.get(model_type)
        if not config:
            raise ModelLoadError(model_type.value, "Missing model config")

        self.models[model_type] = model

        try:
            model_dir = os.path.dirname(config.path)
            tokenizer_path = os.path.join(model_dir, "tokenizer.json")
            tokenizer = PreTrainedTokenizerFast(tokenizer_file=tokenizer_path)
            model.tokenizer = tokenizer
            logger.info(f"✅ Tokenizer for {model_type.value} loaded from {tokenizer_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not load tokenizer for {model_type.value}: {e}")
            model.tokenizer = None

        self.configs[model_type] = config
        logger.info(f"✅ Model {model_type.value} loaded successfully via ModelLoader")

    def generate_response(self, prompt: str, task_type: str = "", context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        model_type = self.current_model

        if context is None:
            context = {}

        if self.memory_manager and ("history" not in context or not context["history"]):
            try:
                context["history"] = self.memory_manager.get_context_history(limit=5)
                used_ids = [e.get("id") for e in context["history"] if "id" in e]
                self.memory_manager.mark_used(used_ids)
                logger.info(f"📥 Injected memory: {[e.get('text', '[no text]') for e in context['history']]}")
            except Exception as e:
                logger.warning(f"⚠️ Memory injection failed: {e}")
                context["history"] = []

        if model_type not in self.models:
            raise ModelLoadError(model_type.value, "Model not loaded")

        if isinstance(prompt, dict):
            prompt = prompt.get("prompt", "")

        full_prompt = self.build_prompt(prompt, model_type, task_type, context)

        model = self.models[model_type]
        tokenizer = getattr(model, "tokenizer", None)
        if tokenizer:
            token_ids = tokenizer.encode(full_prompt)
            if len(token_ids) > (MAX_CONTEXT_LENGTH - SAFE_MARGIN):
                logger.warning(f"⚠️ Prompt length ({len(token_ids)}) exceeds safe limit. Truncating.")
                token_ids = token_ids[-(MAX_CONTEXT_LENGTH - SAFE_MARGIN):]
                full_prompt = tokenizer.decode(token_ids)

        return self.generate(model_type, full_prompt)

    def build_prompt(self, prompt: str, model_type: ModelType, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        memory_summary = ""

        if context and "history" in context:
            entries = context["history"]
            total_entries = len(entries)
            history_limit = 3

            if context.get("force_full_memory") or task_type.lower() == "memory_recall":
                history_limit = total_entries

            summarized = []
            for i, entry in enumerate(entries[-history_limit:]):
                text = entry.get("text") or entry.get("content") or ""
                cleaned = text.strip().replace("\n", " ")
                if len(cleaned) > 200:
                    cleaned = cleaned[:200] + "..."
                summarized.append(f"- {cleaned}")

            if summarized:
                memory_summary = (
                    f"\n🧠 Memory Recall:\n"
                    f"{total_entries} total memory entries found. Showing the {history_limit} most recent:\n"
                    + "\n".join(summarized)
                )

        # Define trigger list and fuzzy matcher
        TOOL_SUMMARY_TRIGGERS = [
            "what can you do", "list your tools", "your capabilities",
            "what are you capable of", "tool summary", "toolbox", "abilities",
            "show me your tools", "available tools", "tools you have"
        ]

        def matches_tool_summary_request(p: str) -> bool:
            p = p.lower()
            return any(phrase in p for phrase in TOOL_SUMMARY_TRIGGERS) or \
                   difflib.get_close_matches(p, TOOL_SUMMARY_TRIGGERS, n=1, cutoff=0.85)

        # Handle tool summary request
        if matches_tool_summary_request(prompt):
            tools = list_tools()
            summary = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])
            memory_capability = """
You have a powerful cognitive memory system that mimics human recall.

- Short-term memory (recent inputs) is automatically injected to maintain conversational flow.
- Long-term memory (persistent storage) is accessible using the `recall_memory` tool.
- Use memory to retrieve facts, track goals, recall emotional tone, or revisit project history.
- You may choose to consult memory proactively - especially when the user refers to "earlier", "before", or "you said".
- If unsure about past details, use the `recall_memory` tool instead of guessing.
"""
            return f"""User: {prompt}

Assistant (thinking): That's a great question. Let me check my tool registry...

Here’s what I can do right now:
{summary}

{memory_capability}"""

        return PromptTemplates.wrap(self.system_prompt + memory_summary, prompt)

    def generate(self, model_type: ModelType, user_prompt: str) -> Dict[str, str]:
        if model_type not in self.models:
            raise ModelLoadError(model_type.value, "Model not loaded")

        model = self.models[model_type]
        config = self.configs[model_type]

        try:
            output = model(
                prompt=user_prompt,
                temperature=config.temperature,
                top_p=config.top_p,
                repeat_penalty=config.repetition_penalty,
                max_tokens=getattr(config, "max_tokens", 256),
                stop=["<|im_end|>", "<|EOT|>"]
            )

            text = output["choices"][0]["text"]
            if "<|im_end|>" in text:
                text = text.split("<|im_end|>")[0].strip() + " <|im_end|>"

            cleaned = ResponseFormatter.extract_final_answer(text)
            if not cleaned:
                cleaned = "[FRIDAY refused to answer due to format violation]\n<|im_end|>"

            affect = "unknown"
            try:
                if hasattr(model, "device") and hasattr(model, "get_input_embeddings"):
                    with torch.no_grad():
                        tokenizer = model.tokenizer
                        input_ids = torch.tensor([tokenizer.encode(user_prompt)]).to(model.device)
                        response_ids = torch.tensor([tokenizer.encode(cleaned)]).to(model.device)
                        input_emb = model.get_input_embeddings()(input_ids).mean(dim=1).squeeze()
                        response_emb = model.get_input_embeddings()(response_ids).mean(dim=1).squeeze()
                        info_gain = cosine(input_emb.cpu().numpy(), response_emb.cpu().numpy())
                        probs = F.softmax(output["logits"], dim=-1)
                        log_probs = torch.log(probs + 1e-12)
                        entropy = -torch.sum(probs * log_probs, dim=-1).mean().item()
                        affect = self.classify_affect(entropy, info_gain)
            except Exception as scoring_error:
                logger.warning(f"⚠️ Error during affect scoring: {scoring_error}")
                affect = "unknown"

            return {"raw": text.strip(), "cleaned": cleaned.strip(), "affect": affect}

        except Exception as e:
            logger.error(f"Error during inference: {e}")
            raise ModelInferenceError(model_type.value, str(e))

    def classify_affect(self, entropy: float, info_gain: float) -> str:
        if entropy < 1.5:
            if info_gain < 0.3:
                return "happy"
            else:
                return "content"
        elif entropy < 3.0:
            if info_gain > 1.0:
                return "curious"
            else:
                return "neutral"
        else:
            if info_gain < 0.3:
                return "sad"
            elif info_gain < 1.0:
                return "anxious"
            else:
                return "surprised"

