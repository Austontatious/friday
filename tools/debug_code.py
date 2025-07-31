import subprocess
import tempfile
import os
from typing import Dict

SUPPORTED_LANGUAGES = {
    "python": {
        "extension": ".py",
        "command": lambda filepath: ["python3", filepath],
    },
    # Extend here: JS, Bash, etc.
}

def debug_code(code: str, language: str = "python") -> Dict:
    """
    Execute code safely in a temp file and return the result.
    Only supports listed languages.
    """
    lang = language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        return {
            "success": False,
            "error": f"Unsupported language: {language}"
        }

    ext = SUPPORTED_LANGUAGES[lang]["extension"]
    command_builder = SUPPORTED_LANGUAGES[lang]["command"]

    try:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=ext, delete=False) as temp_file:
            temp_file.write(code)
            temp_file.flush()
            temp_path = temp_file.name

        result = subprocess.run(
            command_builder(temp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Execution timed out"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

