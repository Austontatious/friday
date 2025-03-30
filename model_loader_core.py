import os
import logging
from typing import Dict, Any, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from llama_cpp import Llama
from model_types import ModelType
from model_config import model_config
from error_handler import ModelLoadError

class ModelLoader:
    def __init__(self):
        self.loaded_models = {}
        
    def is_model_loaded(self, model_type: ModelType) -> bool:
        """Check if a model is already loaded."""
        return model_type.value in self.loaded_models
        
    def load_model(self, model_type: ModelType) -> Dict[str, Any]:
        """Load a specific model type and return model data."""
        if self.is_model_loaded(model_type):
            return self.loaded_models[model_type]
            
        try:
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
                self.loaded_models[model_type.value] = model_data
                return model_data
            else:
                raise ModelLoadError(f"Failed to load model: {model_type.value}")
                
        except Exception as e:
            logging.error(f"Error loading model {model_type.value}: {e}")
            raise ModelLoadError(f"Failed to load model {model_type.value}: {e}")
            
    def unload_model(self, model_type: ModelType) -> None:
        """Unload a specific model type."""
        if model_type.value in self.loaded_models:
            # Clear references to allow garbage collection
            self.loaded_models.pop(model_type.value)
            
    def get_loaded_models(self) -> Dict[str, Any]:
        """Get dictionary of loaded models."""
        return self.loaded_models

# Do NOT create the instance here 