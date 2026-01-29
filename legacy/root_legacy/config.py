import os
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel

# === Model Type Enum ===
class ModelType(Enum):
    MISTRAL = "mistral"
    FRIDAY = "friday"
    LLAMA = "llama"
    DEEPSEEK = "deepseek"
    HUGINN = "huginn"

# === Model Configuration Schema ===
class ModelConfig(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    model_type: Optional[ModelType] = None
    path: str
    capabilities: Optional[List[str]] = []
    context_length: Optional[int] = 4096
    quantized: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    repetition_penalty: Optional[float] = 1.1
    stop: Optional[List[str]] = []
    prompt_style: Optional[str] = "chatml"
    n_gpu_layers: Optional[int] = 0

# === ModelConfigManager ===
class ModelConfigManager:
    def __init__(self):
        self.configs: Dict[ModelType, ModelConfig] = {
            ModelType.DEEPSEEK: ModelConfig(
                path="/workspace/ai-lab/models/deepseek-coder/deepseek-coder-6.7b-instruct-q4_K_M.gguf",
                context_length=16384,
                n_gpu_layers=32
            ),
            ModelType.FRIDAY: ModelConfig(
                path="/workspace/ai-lab/models/Friday_0.2.2.1/friday_q8.gguf",
                context_length=8192,
                n_gpu_layers=32,
                temperature=1.2,
                top_p=0.85,
                repetition_penalty=1.1,
                stop=["<|EOT|>"],
                prompt_style="chatml"
            ),
            ModelType.HUGINN: ModelConfig(
                path="/workspace/ai-lab/models/tinyllama-chat-1.1b/tinyllama-chat-1.1b_q8_0.gguf",
                context_length=2048,
                n_gpu_layers=32,
                temperature=1.5,
                top_p=0.3,
                repetition_penalty=1.0,
                stop=["<|im_end|>", "<|im_start|>"],
                prompt_style="chatml"
            ),
        }

# ✅ Final: create global instance AFTER defining the class
model_config_manager = ModelConfigManager()


