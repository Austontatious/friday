# friday/huginn/core.py

import logging
from typing import Optional
from llama_cpp import Llama
from friday.config import model_config_manager, ModelType
from friday.error_handler import ModelLoadError, ModelInferenceError

logger = logging.getLogger("huginn")

_model: Optional[Llama] = None
_config = model_config_manager.configs[ModelType.HUGINN]

SYSTEM_PROMPT_SINGLE = """
You are Huginn, FRIDAY's symbolic imagination core.
Respond with a single bold, speculative, or emotionally rich idea to the user's prompt.
""".strip()

SYSTEM_PROMPT_STREAM = """
You are Huginn, FRIDAY's imagination engine.
Respond with a stream of symbolic, surreal, and emotionally layered ideas.
Offer multiple conflicting interpretations or visions.
Generate until you run out of creative energy or tokens.
""".strip()


def load():
    global _model
    if _model is not None:
        return _model

    try:
        _model = Llama(
            model_path=_config.path,
            n_ctx=_config.context_length or 2048,
            n_threads=12,
            n_gpu_layers=_config.n_gpu_layers or 0,
            use_mmap=True,
            use_mlock=False,
            use_flash_attention=True
        )
        return _model

    except Exception as e:
        raise ModelInferenceError(ModelType.HUGINN.value, str(e))


def generate_idea(prompt: str, stream: bool = False) -> str:
    print("\n🚨 HUGINN CALLED 🚨\n")

    model = load()

    system_prompt = SYSTEM_PROMPT_STREAM if stream else SYSTEM_PROMPT_SINGLE

    full_prompt = "\n".join([
        "<|im_start|>system", system_prompt, "<|im_end|>",
        "<|im_start|>user", prompt.strip(), "<|im_end|>",
        "<|im_start|>assistant"
    ])

    try:
        output = model(
            prompt=full_prompt,
            temperature=_config.temperature,
            top_p=_config.top_p,
            repeat_penalty=_config.repetition_penalty,
            max_tokens=_config.context_length - len(full_prompt.split()),
            stop=_config.stop
        )

        raw = output["choices"][0]["text"].strip()

        # ✅ Log Huginn’s raw imagination to terminal
        print("\n" + "=" * 60)
        print("🎭 HUGINN RAW STREAMED OUTPUT:")
        print("-" * 60)
        print(raw)
        print("=" * 60 + "\n")

        return raw

    except Exception as e:
        raise ModelInferenceError(ModelType.HUGINN.value, str(e))

