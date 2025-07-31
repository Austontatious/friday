from models.deepseek_agent import DeepSeekClient
from utils.testing import test_code_snippet

deepseek = DeepSeekClient()

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
