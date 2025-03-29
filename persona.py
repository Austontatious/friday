from typing import Dict, List, Optional, Any
import json
import os
from enum import Enum
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import onnxruntime
from tenacity import retry, stop_after_attempt, wait_exponential

class ModelType(Enum):
    DEEPSEEK = "deepseek-coder-6.7b"
    CLAUDE = "claude-2"
    CHAT_O1 = "chat-o1"

class PersonaManager:
    def __init__(self):
        self.model_configs = {
            ModelType.DEEPSEEK: {
                "name": "DeepSeek Coder 6.7B",
                "supported_tasks": ["code_explanation", "code_generation", "debugging"],
                "confidence_threshold": 0.75,
                "max_tokens": 2048,
                "temperature": 0.7
            },
            ModelType.CLAUDE: {
                "name": "Claude 2",
                "supported_tasks": ["code_explanation", "documentation", "general_conversation"],
                "confidence_threshold": 0.65,
                "max_tokens": 4096,
                "temperature": 0.8
            },
            ModelType.CHAT_O1: {
                "name": "Chat O1",
                "supported_tasks": ["general_conversation", "code_explanation"],
                "confidence_threshold": 0.60,
                "max_tokens": 1024,
                "temperature": 0.9
            }
        }
        self.current_model = None
        self.model_cache = {}
        self._initialize_models()

    def _initialize_models(self):
        """Initialize model instances and ONNX runtime."""
        try:
            # Initialize ONNX runtime
            self.ort_session = onnxruntime.InferenceSession(
                "models/deepseek-coder-6.7b.onnx",
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            
            # Load model configurations
            for model_type in ModelType:
                self._load_model(model_type)
                
        except Exception as e:
            logging.error(f"Error initializing models: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _load_model(self, model_type: ModelType):
        """Load a model with retry logic."""
        try:
            if model_type == ModelType.DEEPSEEK:
                # Use ONNX runtime for DeepSeek
                self.model_cache[model_type] = self.ort_session
            else:
                # Load other models through transformers
                model_name = model_type.value
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto"
                )
                self.model_cache[model_type] = {
                    "model": model,
                    "tokenizer": tokenizer
                }
        except Exception as e:
            logging.error(f"Error loading model {model_type.value}: {e}")
            raise

    def get_prompt_for_task(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate appropriate prompt based on task type and context."""
        base_prompts = {
            "code_explanation": "Explain the following code in detail:\n{code}",
            "code_generation": "Generate code for the following task:\n{task}",
            "debugging": "Debug the following code and suggest fixes:\n{code}",
            "documentation": "Generate documentation for the following code:\n{code}",
            "general_conversation": "Respond to the following query:\n{query}"
        }
        
        prompt_template = base_prompts.get(task_type, base_prompts["general_conversation"])
        
        if context:
            # Enhance prompt with context
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            prompt_template = f"Context:\n{context_str}\n\n{prompt_template}"
            
        return prompt_template

    def select_model(self, task_type: str, confidence_score: float) -> ModelType:
        """Select appropriate model based on task type and confidence score."""
        for model_type, config in self.model_configs.items():
            if (task_type in config["supported_tasks"] and 
                confidence_score >= config["confidence_threshold"]):
                return model_type
        
        # Fallback to Claude for general tasks
        return ModelType.CLAUDE

    def generate_response(self, prompt: str, task_type: str, confidence_score: float) -> str:
        """Generate response using appropriate model."""
        model_type = self.select_model(task_type, confidence_score)
        model_config = self.model_configs[model_type]
        
        try:
            if model_type == ModelType.DEEPSEEK:
                # Use ONNX runtime for DeepSeek
                inputs = self.model_cache[model_type].get_inputs()
                outputs = self.model_cache[model_type].run(
                    None,
                    {"input": prompt}
                )
                response = outputs[0]
            else:
                # Use transformers for other models
                model_data = self.model_cache[model_type]
                inputs = model_data["tokenizer"](
                    prompt,
                    return_tensors="pt",
                    max_length=model_config["max_tokens"],
                    truncation=True
                )
                
                outputs = model_data["model"].generate(
                    **inputs,
                    max_length=model_config["max_tokens"],
                    temperature=model_config["temperature"],
                    do_sample=True
                )
                
                response = model_data["tokenizer"].decode(outputs[0], skip_special_tokens=True)
            
            return response
            
        except Exception as e:
            logging.error(f"Error generating response with {model_type.value}: {e}")
            # Fallback to Claude
            return self._fallback_to_claude(prompt)

    def _fallback_to_claude(self, prompt: str) -> str:
        """Fallback to Claude model when primary model fails."""
        try:
            model_data = self.model_cache[ModelType.CLAUDE]
            inputs = model_data["tokenizer"](
                prompt,
                return_tensors="pt",
                max_length=self.model_configs[ModelType.CLAUDE]["max_tokens"],
                truncation=True
            )
            
            outputs = model_data["model"].generate(
                **inputs,
                max_length=self.model_configs[ModelType.CLAUDE]["max_tokens"],
                temperature=self.model_configs[ModelType.CLAUDE]["temperature"],
                do_sample=True
            )
            
            return model_data["tokenizer"].decode(outputs[0], skip_special_tokens=True)
            
        except Exception as e:
            logging.error(f"Error in Claude fallback: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again later."

    def get_model_capabilities(self, model_type: ModelType) -> Dict[str, Any]:
        """Get capabilities of a specific model."""
        return self.model_configs.get(model_type, {})

    def update_model_config(self, model_type: ModelType, config: Dict[str, Any]):
        """Update configuration for a specific model."""
        if model_type in self.model_configs:
            self.model_configs[model_type].update(config)
            return True
        return False

