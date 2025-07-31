import os
import re

BASE_DIR = "/workspace/ai-lab/friday"
KNOWN_LOCAL_MODULES = {
    "model_config", "task_manager", "context", "memory", "persona",
    "model_loader_core", "model_types", "config", "backend_core"
}

import_pattern = re.compile(r"^(from|import)\s+([.\w]+)")

seen = set()
issues = []

for file in os.listdir(BASE_DIR):
    if not file.endswith(".py"):
        continue

    path = os.path.join(BASE_DIR, file)

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            lines = f.readlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        match = import_pattern.match(stripped)
        if not match:
            continue

        _, mod = match.groups()

        if mod.startswith(".") or mod.split(".")[0] in KNOWN_LOCAL_MODULES:
            key = (file, i, mod)
            if key not in seen:
                issues.append(f"{file}:{i} → {stripped}")
                seen.add(key)

# Output
print("\n🔍 Top-Level Import Issues in /friday/:\n")
for issue in issues:
    print(issue)

