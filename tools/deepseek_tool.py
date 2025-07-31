# friday/tools/deepseek_tool.py

from friday.model_loader_core import initialize_model_loader
from friday.model_types import ModelType
import logging

logger = logging.getLogger("tool.deepseek")

# Initialize the DeepSeek model from the global model loader
model = initialize_model_loader().get(ModelType.DEEPSEEK)

def analyze_code(prompt: str) -> str:
    """
    Uses the DeepSeek model to generate, debug, or refactor code based on the given prompt.
    """
    if not model:
        logger.warning("⚠️ DeepSeek model not available.")
        return "[DeepSeek is unavailable right now.]"

    try:
        result = model(
            prompt=prompt,
            temperature=0.2,  # Controlled creativity for code
            top_p=0.95,
            repeat_penalty=1.1,
            max_tokens=1024,
            stop=["<|im_end|>", "<|EOT|>"]
        )
        output = result["choices"][0]["text"].strip()
        logger.info("✅ DeepSeek produced output.")
        return output

    except Exception as e:
        logger.error(f"❌ DeepSeek tool error: {e}")
        return "[DeepSeek encountered an error while analyzing your request.]"

