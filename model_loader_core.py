# friday/model_loader_core.py

import os
import logging
from llama_cpp import Llama
from .model_config import model_config, ModelType, ModelConfig

logger = logging.getLogger("friday")
logger.setLevel(logging.INFO)

class ModelLoader:
    def __init__(self):
        self.models: dict[ModelType, Llama] = {}
        self.failed_models: dict[ModelType, str] = {}

        logger.info("🔍 Initializing ModelLoader...")

        for model_type, cfg in model_config.configs.items():
            try:
                model = self._load_llama_model(cfg)
                self.models[model_type] = model
                logger.info(f"✅ Loaded model: {model_type.value}")
            except Exception as e:
                self.failed_models[model_type] = str(e)
                logger.error(f"❌ Failed to load model '{model_type.value}': {e}")

        if not self.models:
            logger.warning("⚠️ No models were loaded successfully.")

    def _load_llama_model(self, cfg: ModelConfig) -> Llama:
        if not os.path.exists(cfg.path):
            raise FileNotFoundError(f"Model file not found at {cfg.path}")

        use_gpu = os.environ.get("USE_CUDA", "false").lower() == "true"
        logger.debug(f"🧠 Loading LLaMA model from {cfg.path} (GPU: {use_gpu})")

        return Llama(
            model_path=cfg.path,
            n_ctx=cfg.context_length,
            n_batch=512,
            use_mlock=False,
            n_gpu_layers=cfg.n_gpu_layers if use_gpu else 0,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            repeat_penalty=cfg.repetition_penalty,
            stop=cfg.stop,
            verbose=True,
        )

    def get(self, model_type: ModelType) -> Llama | None:
        if model_type in self.models:
            return self.models[model_type]
        if model_type in self.failed_models:
            logger.warning(f"⚠️ Attempted to access failed model '{model_type.value}': {self.failed_models[model_type]}")
        return None

    def list_models(self) -> list[str]:
        return [mt.value for mt in self.models.keys()]

    def get_failures(self) -> dict[str, str]:
        return {mt.value: err for mt, err in self.failed_models.items()}


# 🔁 Singleton-like initializer
_model_loader_instance: ModelLoader | None = None

def initialize_model_loader() -> ModelLoader:
    global _model_loader_instance
    if _model_loader_instance is None:
        _model_loader_instance = ModelLoader()
    return _model_loader_instance

