import os
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from config import config
from model_types import ModelType

@dataclass
class TokenConfig:
    bos_token_id: int
    eos_token_id: int
    eot_token_id: int
    pad_token_id: int
    special_tokens: Dict[str, str]
    special_eog_ids: List[int]
    special_eos_ids: List[int]
    special_bos_ids: List[int]
    special_pad_ids: List[int]

@dataclass
class ModelConfig:
    name: str
    token_config: TokenConfig
    architecture: str = "llama"
    context_length: int = 16384
    embedding_length: int = 4096
    feed_forward_length: int = 11008
    attention_head_count: int = 32
    attention_head_count_kv: int = 32
    block_count: int = 32
    rope_dimension_count: int = 128
    rope_freq_base: float = 100000.0
    rope_scale_linear: float = 4.0
    layer_norm_rms_epsilon: float = 0.000001
    tokenizer_model: str = "gpt2"

class ModelConfigManager:
    def __init__(self):
        self.configs: Dict[str, ModelConfig] = {
            ModelType.DEEPSEEK.value: ModelConfig(
                name="deepseek-ai_deepseek-coder-6.7b-instruct",
                token_config=TokenConfig(
                    bos_token_id=32013,
                    eos_token_id=32021,
                    eot_token_id=32014,
                    pad_token_id=32014,
                    special_tokens={
                        "bos": "REDACTED_SPECIAL_TOKEN",
                        "eos": "REDACTED_SPECIAL_TOKEN",
                        "eot": "REDACTED_SPECIAL_TOKEN",
                        "pad": "REDACTED_SPECIAL_TOKEN",
                        "fim_prefix": "REDACTED_SPECIAL_TOKEN",
                        "fim_suffix": "REDACTED_SPECIAL_TOKEN",
                        "fim_middle": "REDACTED_SPECIAL_TOKEN"
                    },
                    special_eog_ids=[32014, 32021],
                    special_eos_ids=[32021],
                    special_bos_ids=[32013],
                    special_pad_ids=[32014]
                ),
                context_length=16384,
                embedding_length=4096
            ),
            ModelType.LLAMA.value: ModelConfig(
                name="llama-2-7b-chat",
                token_config=TokenConfig(
                    bos_token_id=1,
                    eos_token_id=2,
                    eot_token_id=2,
                    pad_token_id=0,
                    special_tokens={
                        "bos": "<s>",
                        "eos": "</s>",
                        "eot": "</s>",
                        "pad": "<pad>"
                    },
                    special_eog_ids=[2],
                    special_eos_ids=[2],
                    special_bos_ids=[1],
                    special_pad_ids=[0]
                ),
                context_length=4096,
                embedding_length=4096
            )
        }
        
        self._validate_configs()
        
    def _validate_configs(self) -> None:
        """Validate model configurations."""
        models_to_remove = []
        
        for model_name, model_config in self.configs.items():
            # First check if model exists
            model_path = getattr(config, f"{model_name.upper()}_MODEL_PATH", None)
            if not os.path.exists(model_path):
                if model_name == ModelType.DEEPSEEK.value:
                    raise FileNotFoundError(f"{model_name} model not found at {model_path}")
                else:
                    logging.warning(f"{model_name} model not found at {model_path}. Some features may be limited.")
                    models_to_remove.append(model_name)
                    continue  # Skip further validation for models to be removed
                    
            # Validate special tokens
            if model_config.token_config.eos_token_id not in model_config.token_config.special_eos_ids:
                raise ValueError(f"{model_name} EOS token not in special tokens")
            if model_config.token_config.eot_token_id not in model_config.token_config.special_eog_ids:
                logging.warning(f"{model_name} EOT token not in special tokens - fixing")
                # Add the token to the list
                model_config.token_config.special_eog_ids.append(model_config.token_config.eot_token_id)
                
            # Validate context length
            if model_config.context_length < 2048:
                logging.warning(f"{model_name} context length ({model_config.context_length}) is less than recommended minimum (2048)")
        
        # Remove models after iteration
        for model_name in models_to_remove:
            self.configs.pop(model_name)
        
    def get_model_config(self, model_type: str) -> ModelConfig:
        """Get configuration for a specific model type."""
        if model_type not in self.configs:
            raise ValueError(f"Model type {model_type} not found")
        return self.configs[model_type]
        
    def get_token_config(self, model_type: str) -> TokenConfig:
        """Get token configuration for a specific model type."""
        return self.get_model_config(model_type).token_config
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to dictionary for logging/debugging."""
        return {
            model_name: {
                "name": config.name,
                "architecture": config.architecture,
                "context_length": config.context_length,
                "token_config": {
                    "bos_token_id": config.token_config.bos_token_id,
                    "eos_token_id": config.token_config.eos_token_id,
                    "eot_token_id": config.token_config.eot_token_id,
                    "pad_token_id": config.token_config.pad_token_id,
                    "special_eog_ids": config.token_config.special_eog_ids,
                    "special_eos_ids": config.token_config.special_eos_ids,
                    "special_bos_ids": config.token_config.special_bos_ids,
                    "special_pad_ids": config.token_config.special_pad_ids
                }
            }
            for model_name, config in self.configs.items()
        }

# Create global config instance
model_config = ModelConfigManager() 