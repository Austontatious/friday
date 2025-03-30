from typing import Dict, List, Optional, Any
import json
import os
import logging
import time
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from llama_cpp import Llama
from tenacity import retry, stop_after_attempt, wait_exponential
from model_config import model_config
from prompt_templates import prompt_templates
from response_formatter import response_formatter
from error_handler import error_handler, ModelError, ModelLoadError, ModelInferenceError, ModelConfigError
from model_monitor import model_monitor
from model_cache import model_cache
from rate_limiter import rate_limiter
from model_types import ModelType

class PersonaManager:
    def __init__(self):
        self.models: Dict[ModelType, Any] = {}
        self.tokenizers: Dict[ModelType, Any] = {}
        self.model_configs: Dict[ModelType, Any] = {}
        self._initialize_models()
        
    def load_model(self, model_type: ModelType) -> Dict[str, Any]:
        """Load a specific model type and return model data."""
        try:
            # Check if model already loaded
            if model_type in self.models:
                return {
                    "model": self.models[model_type],
                    "tokenizer": self.tokenizers.get(model_type),
                    "config": self.model_configs.get(model_type)
                }
                
            # Get model configuration
            config = model_config.get_model_config(model_type.value)
            
            # Load appropriate model based on type
            model_data = None
            
            if model_type == ModelType.DEEPSEEK:
                model_path = os.getenv("DEEPSEEK_MODEL_PATH", "models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf")
                if not os.path.exists(model_path):
                    raise ModelLoadError(f"DeepSeek model not found at {model_path}")
                    
                # Load using llama.cpp
                model = Llama(
                    model_path=model_path,
                    n_ctx=config.context_length,
                    n_batch=512,
                    verbose=True
                )
                
                model_data = {
                    "model": model,
                    "tokenizer": None,  # Llama models have built-in tokenization
                    "config": config
                }
            
            # Store model data for reuse
            if model_data:
                self.models[model_type] = model_data["model"]
                self.tokenizers[model_type] = model_data["tokenizer"]
                self.model_configs[model_type] = model_data["config"]
                return model_data
            else:
                raise ModelLoadError(f"Failed to load model: {model_type.value}")
                
        except Exception as e:
            logging.error(f"Error loading model {model_type.value}: {e}")
            raise ModelLoadError(f"Failed to load model {model_type.value}: {e}")
    
    def _initialize_models(self) -> None:
        """Initialize models with proper error handling."""
        try:
            # Only try to load DEEPSEEK model by default
            try:
                model_data = self.load_model(ModelType.DEEPSEEK)
                logging.info(f"Successfully loaded {ModelType.DEEPSEEK.value} model")
            except ModelLoadError as e:
                logging.error(f"Failed to load {ModelType.DEEPSEEK.value} model: {e}")
                # Clear any partial state
                self.models.pop(ModelType.DEEPSEEK, None)
                self.tokenizers.pop(ModelType.DEEPSEEK, None)
                self.model_configs.pop(ModelType.DEEPSEEK, None)
            except Exception as e:
                logging.error(f"Unexpected error loading {ModelType.DEEPSEEK.value} model: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to initialize models: {e}")
            
    def _get_model_capabilities(self, config: Any) -> Dict[str, Any]:
        """Get capabilities for a specific model."""
        return {
            "context_length": config.context_length,
            "embedding_length": config.embedding_length,
            "attention_heads": config.attention_head_count,
            "token_config": {
                "bos_token_id": config.token_config.bos_token_id,
                "eos_token_id": config.token_config.eos_token_id,
                "eot_token_id": config.token_config.eot_token_id,
                "pad_token_id": config.token_config.pad_token_id,
                "max_token_length": config.token_config.max_token_length
            }
        }
        
    def get_model_capabilities(self, model_type: ModelType) -> Dict[str, Any]:
        """Get capabilities for a specific model type."""
        if model_type not in self.models:
            raise ModelConfigError(f"Model type {model_type} not available")
        return self.model_configs[model_type].capabilities
        
    def get_model_config(self, model_type: ModelType) -> Any:
        """Get configuration for a specific model type."""
        if model_type not in self.model_configs:
            raise ModelConfigError(f"Model type {model_type} not available")
        return self.model_configs[model_type]
        
    def get_token_config(self, model_type: ModelType) -> Any:
        """Get token configuration for a specific model type."""
        return self.get_model_config(model_type).token_config
        
    def validate_model_input(self, model_type: ModelType, input_text: str) -> bool:
        """Validate input text against model constraints."""
        config = self.get_model_config(model_type)
        token_config = config.token_config
        
        # Check input length
        if len(input_text) > token_config.max_token_length * 4:  # Rough estimate
            logging.warning(f"Input text exceeds maximum token length for {model_type}")
            return False
            
        return True
        
    def get_available_models(self) -> List[ModelType]:
        """Get list of available model types."""
        return list(self.models.keys())
        
    def get_model_info(self, model_type: ModelType) -> Dict[str, Any]:
        """Get detailed information about a specific model."""
        if model_type not in self.models:
            raise ModelConfigError(f"Model type {model_type} not available")
            
        model_data = self.models[model_type]
        config = self.model_configs[model_type]
        
        return {
            "type": model_type.value,
            "name": config.name,
            "architecture": config.architecture,
            "capabilities": self._get_model_capabilities(config),
            "tokenizer": {
                "model": config.tokenizer_model,
                "special_tokens": config.token_config.special_tokens
            }
        }

    def get_prompt_for_task(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get appropriate prompt for a specific task type."""
        try:
            model_type = self.select_model(task_type, 0.8)  # Default confidence score
            return prompt_templates.get_model_specific_prompt(model_type, task_type, **context)
        except Exception as e:
            logging.error(f"Error getting prompt for task: {e}")
            raise ModelError(f"Failed to get prompt for task: {e}")

    def select_model(self, task_type: str, confidence_score: float = 0.8) -> ModelType:
        """Select the most appropriate model for a given task."""
        try:
            # For now, always use DeepSeek since other models are not available
            if ModelType.DEEPSEEK in self.models:
                return ModelType.DEEPSEEK
            
            # Check if model file exists
            if ModelType.DEEPSEEK not in self.model_configs:
                model_path = os.getenv("DEEPSEEK_MODEL_PATH", "models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf")
                if not os.path.exists(model_path):
                    raise ModelLoadError(f"DeepSeek model not found at {model_path}")
                
                # Try to load the model
                self.load_model(ModelType.DEEPSEEK)
                return ModelType.DEEPSEEK
            
            logging.error("No models available")
            raise ModelLoadError("No models available")
            
        except Exception as e:
            logging.error(f"Error selecting model: {e}")
            raise ModelError(f"Failed to select model: {e}")

    def generate_response(self, prompt: str, task_type: str = "general") -> str:
        """Generate a response using the appropriate model."""
        try:
            # Check cache first
            cached_response = model_cache.get(self.select_model(task_type), prompt, task_type=task_type)
            if cached_response:
                logging.info("Found cached response")
                return response_formatter.format_model_response(self.select_model(task_type), cached_response['text'])
            
            # Select model based on task type
            model_type = self.select_model(task_type)
            
            # Check rate limits
            if not rate_limiter.can_make_request(model_type):
                raise ModelInferenceError("Rate limit exceeded")
                
            # Log request
            model_monitor.log_request(model_type, task_type)
            
            # Update model status
            model_monitor.update_model_status(model_type, True)
            
            try:
                # Generate response
                start_time = time.time()
                
                if model_type not in self.models:
                    raise ModelLoadError(f"Model {model_type.value} is not loaded")
                
                model = self.models[model_type]
                
                # Get model-specific prompt
                model_prompt = prompt_templates.get_model_specific_prompt(model_type, task_type, user_prompt=prompt)
                
                # Generate response with DeepSeek
                response = model.generate(
                    model_prompt,
                    max_tokens=2048,
                    temperature=0.7,
                    top_p=0.95,
                    stop=["<|EOT|>", ""],
                )
                
                # Extract raw response
                raw_response = response.get('choices', [{}])[0].get('text', '')
                
                # Log token usage
                input_tokens = len(model_prompt.split())
                output_tokens = len(raw_response.split())
                model_monitor.log_token_usage(model_type, input_tokens, output_tokens)
                
                # Log latency
                model_monitor.log_latency(model_type, task_type, start_time)
                
                # Cache response
                model_cache.set(model_type, prompt, {'text': raw_response, 'timestamp': time.time()}, task_type=task_type)
                
                # Format response
                return response_formatter.format_model_response(model_type, raw_response)
                
            finally:
                # Update model status
                model_monitor.update_model_status(model_type, ModelType.DEEPSEEK in self.models)
                
                # Release request
                rate_limiter.release_request(model_type)
                
        except ModelError as e:
            model_monitor.log_error(model_type, "inference" if isinstance(e, ModelInferenceError) else "model_load", e)
            return response_formatter.format_error_response(e)
        except Exception as e:
            logging.error(f"Unexpected error generating response: {e}")
            return response_formatter.format_error_response(e)

# Create global persona manager instance
persona_manager = PersonaManager()

