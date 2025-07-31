# fix_broken_imports.py
import os
import re
from pathlib import Path

# 👇 Corrected to point to actual Friday root
FRIDAY_DIR = Path(__file__).resolve().parent.parent

IMPORT_REGEX = re.compile(r"^from\s+([a-zA-Z0-9_]+)\s+import\s+")

files_to_fix = [
    "context.py",
    "error_handler.py",
    "persona.py",
    "codebase_reader.py",
    "process_manager.py",
    "task_manager.py",
    "model_loader_core.py",
    "prompt_templates.py",
    "response_formatter.py",
    "rate_limiter.py",
    "model_monitor.py",
    "model_cache.py",
    "server.py",
    "friday_routes.py",
]

def fix_imports():
    for filename in files_to_fix:
        file_path = FRIDAY_DIR / filename
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        modified = False
        new_lines = []
        for line in lines:
            match = IMPORT_REGEX.match(line)
            if match:
                imported_module = match.group(1)
                # Avoid modifying built-ins or relative imports
                if not imported_module.startswith((".", "os", "sys", "fastapi", "uvicorn", "datetime", "socket", "logging")):
                    line = line.replace(f"from {imported_module}", f"from .{imported_module}")
                    modified = True
            new_lines.append(line)

        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"✅ Fixed imports in {file_path.name}")
        else:
            print(f"✅ No changes needed in {file_path.name}")

if __name__ == "__main__":
    fix_imports()

