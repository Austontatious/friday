# friday/model_cache.py

import os
from llama_cpp import Llama
from .model_config import ModelType, model_config

# Central model cache that holds loaded LLaMA models
model_cache = {}

def load_model(model_type: ModelType):
    """
    Load a model of the given type into the cache if not already loaded.
    """
    if model_type in model_cache:
        return model_cache[model_type]

    config = model_config[model_type]
    model_path = config.get("quantized_model_path") or config.get("path")
    context_length = config.get("context_length", 4096)
    n_gpu_layers = config.get("n_gpu_layers", 0)

    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    print(f"🧠 Loading model: {model_type.value} from {model_path}")
    llm = Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=context_length,
        use_mlock=True,
        verbose=False
    )
    model_cache[model_type] = llm
    return llm

def get_model(model_type: ModelType) -> Llama:
    """
    Retrieve a model from the cache.
    """
    if model_type not in model_cache:
        raise ValueError(f"Model {model_type.value} not loaded.")
    return model_cache[model_type]

def unload_model(model_type: ModelType):
    """
    Remove a model from cache to free memory.
    """
    if model_type in model_cache:
        del model_cache[model_type]

def clear_cache():
    """
    Clear all models from cache.
    """
    model_cache.clear()

