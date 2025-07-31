from models.deepseek_agent import DeepSeekClient
from utils.testing import test_code_snippet

deepseek = DeepSeekClient()

def debug_code(code: str, language: str = "python", error_message: str = "", filename: str = "") -> dict:
    """
    Debug code with DeepSeek. Optionally uses an error message or log.
    """
    system_prompt = f"""
You are an expert debugging assistant. Your job is to find the error in the following {language} code and fix it.
Explain what the issue was, how you fixed it, and return the corrected code.
"""

    prompt = f"""Filename: {filename or 'unknown_file'}
Language: {language}
Error Message:
{error_message}

Code to Debug:
```{language}
{code}
```

Respond in this JSON format:
{{
  "fixed_code": "...",
  "explanation": "...",
  "error_summary": "..."
}}
"""

    response = deepseek.generate(system=system_prompt, prompt=prompt, format="json")

    test_result = test_code_snippet(response.get("fixed_code", ""), language)

    return {
        "fixed_code": response.get("fixed_code", ""),
        "explanation": response.get("explanation", ""),
        "error_summary": response.get("error_summary", ""),
        "test_result": test_result,
    }
