import os
import re

# -------- SETTINGS -------- #
ROOT_DIR = "/home/mnt/ai-lab/friday"  # Fixed missing quote
IMPORT_LINE = 'from models_config import MODEL_REGISTRY\n'

REPLACEMENTS = {
    r'"?(models/)?phi-2\\.Q4_K_M\\.gguf"?': 'MODEL_REGISTRY["phi"]',
    r'"?/mnt/dev-models/phi-3/phi-3-mini-4k-instruct-q5_k_m\\.gguf"?': 'MODEL_REGISTRY["phi"]',
    r'"?/mnt/dev-models/deepseek-coder/deepseek-coder-6.7b-instruct-q4_k_m\\.gguf"?': 'MODEL_REGISTRY["deepseek"]',
    r'"?/mnt/dev-models/mixtral/mixtral-8x7b-v0.1.Q3_K_M\\.gguf"?': 'MODEL_REGISTRY["mixtral"]'
}
# -------------------------- #

candidates = []

def file_needs_patch(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return any(re.search(pattern, content) for pattern in REPLACEMENTS.keys())

def patch_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified = False
    new_lines = []

    has_import = any("from models_config import MODEL_REGISTRY" in line for line in lines)

    for line in lines:
        if not line.strip().startswith("#"):  # Avoid patching commented lines
            for pattern, registry_ref in REPLACEMENTS.items():
                if re.search(pattern, line):
                    line = re.sub(pattern, registry_ref, line)
                    modified = True
        new_lines.append(line)

    if modified:
        if not has_import:
            new_lines.insert(0, IMPORT_LINE)

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        return True
    return False

# Scan for candidate files
for root, _, files in os.walk(ROOT_DIR):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            if file_needs_patch(full_path):
                candidates.append(full_path)

# Show list and ask for confirmation
if not candidates:
    print("No files found with hardcoded model paths.")
    exit()

print("The following files will be patched:")
for c in candidates:
    print(f" - {c}")

confirm = input("\nProceed with patching these files? (y/n): ").strip().lower()
if confirm != 'y':
    print("Aborted.")
    exit()

# Perform patching
patched_files = [f for f in candidates if patch_file(f)]

print("\n✅ Patch Complete")
for f in patched_files:
    print(f" - {f}")

