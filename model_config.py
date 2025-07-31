from enum import Enum
from typing import Dict

class ModelType(Enum):
    DEEPSEEK = "deepseek"
    HUGINN = "huginn"
    FRIDAY = "friday"  # ✅ add this


class ModelConfig:
    def __init__(self, path: str, context_length: int = 2048, n_gpu_layers: int = 32,
                 temperature: float = 0.7, top_p: float = 0.9, repetition_penalty: float = 1.1,
                 stop: list = None, prompt_style: str = "chatml", max_tokens: int = 256):  # <--- ADD THIS
        self.path = path
        self.context_length = context_length
        self.n_gpu_layers = n_gpu_layers
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.stop = stop or []
        self.prompt_style = prompt_style
        self.max_tokens = max_tokens  # <--- ADD THIS


class ModelConfigManager:
    def __init__(self):
        self.configs: Dict[ModelType, ModelConfig] = {
            
            ModelType.DEEPSEEK: ModelConfig(
                path="/workspace/ai-lab/models/deepseek-coder-merged/deepseek_6.7b_merged_q8_0.gguf",
                context_length=16384,
                n_gpu_layers=32
            ),
            ModelType.FRIDAY: ModelConfig(
                path="/workspace/ai-lab/models/Friday_0.2.2.1/friday_Q6_K.gguf",
                context_length=8192,
                n_gpu_layers=32,
                temperature=1.2,
                top_p=0.85,
                repetition_penalty=1.1,
                stop=["<|EOT|>"],
                prompt_style="chatml",
                max_tokens=1024  # <--- Adjust to desired output length
            ),

            ModelType.HUGINN: ModelConfig(
                path="/workspace/ai-lab/models/tinyllama-chat-1.1b/tinyllama-chat-1.1b_q8_0.gguf",  # ✅ update if different
                context_length=2048,
                n_gpu_layers=32,
                temperature=1.5,
                top_p=0.3,
                repetition_penalty=1.0,
                stop=["<|im_end|>", "<|im_start|>"],
                prompt_style="chatml"
            ),


        }

    def get(self, model_type: ModelType) -> ModelConfig:
        return self.configs[model_type]

model_config = ModelConfigManager()

