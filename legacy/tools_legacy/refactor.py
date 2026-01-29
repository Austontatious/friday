import os
from llama_cpp import Llama

DEEPSEEK_PATH = "/workspace/ai-lab/models/deepseek-coder/deepseek-coder-6.7b-instruct-q4_K_M.gguf"

class DeepSeekClient:
    def __init__(self):
        if not os.path.isfile(DEEPSEEK_PATH):
            raise FileNotFoundError(f"DeepSeek model not found at {DEEPSEEK_PATH}")
        self.model = Llama(
            model_path=DEEPSEEK_PATH,
            n_ctx=4096,
            n_gpu_layers=-1,  # use as much VRAM as possible
            verbose=False
        )

    def generate(self, system: str, prompt: str, format: str = "json") -> dict:
        full_prompt = f"<|system|>\n{system.strip()}\n<|user|>\n{prompt.strip()}\n<|assistant|>"
        response = self.model(full_prompt, stop=["<|user|>", "<|end|>"], max_tokens=1024)
        text = response["choices"][0]["text"].strip()

        try:
            import json
            return json.loads(text)
        except Exception as e:
            return {
                "refactored_code": "",
                "explanation": "Failed to parse JSON output.",
                "diff_summary": "",
                "error": str(e),
                "raw_output": text
            }


def refactor_code(code: str, language: str = "python", filename: str = "", style: str = "best_practices") -> dict:
    """
    Refactor code using DeepSeek and run sanity test if language is supported.
    """
    system_prompt = f"""
You are a senior software engineer. Refactor the following {language} code to improve {style}.
Do not alter functionality. Apply clean coding principles and return the refactored code only.
"""

    prompt = f"""Filename: {filename or 'unknown_file'}
Language: {language}
Refactor Style: {style}

```{language}
{code}
```

Respond in this JSON format:
{{
  "refactored_code": "...",
  "explanation": "...",
  "diff_summary": "..."
}}
"""

    response = deepseek.generate(system=system_prompt, prompt=prompt, format="json")

    # Run built-in test if supported
    test_result = test_code_snippet(response.get("refactored_code", ""), language)

    return {
        "refactored_code": response.get("refactored_code", ""),
        "explanation": response.get("explanation", ""),
        "diff_summary": response.get("diff_summary", ""),
        "test_result": test_result,
    }
