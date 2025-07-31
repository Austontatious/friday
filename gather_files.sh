#!/bin/bash

output_file="FRIDAY_FULL_CODE.txt"

# List of files to gather
files=(
    "friday.py"
    "context.py"
    "memory.py"
    "persona.py"
    "models_config.py"
    "model_types.py"
    "model_loader.py"
    "model_loader_core.py"
    "model_monitor.py"
    "friday_routes.py"
    "task_manager.py"
    "error_handler.py"
    "rate_limiter.py"
    "template_loader.py"
    "server.py"
    "friday_test.py"
    "tests/test_memory.py"
    "tests/test_model_switching.py"
    "tests/__init__.py"
    "start.sh"
    "check-files.sh"
    "patch_files.py"
    "train_all_models.py"
    "download_datasets.py"
    "requirements.txt"
    "README.md"
    ".env.example"
    ".env"
)

# Create or clear the output file
> "$output_file"

# Gather each file
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "============================================" >> "$output_file"
        echo "File: $file" >> "$output_file"
        echo "============================================" >> "$output_file"
        echo "" >> "$output_file"
        cat "$file" >> "$output_file"
        echo "" >> "$output_file"
        echo "" >> "$output_file"
    else
        echo "============================================" >> "$output_file"
        echo "File not found: $file" >> "$output_file"
        echo "============================================" >> "$output_file"
        echo "" >> "$output_file"
    fi
done 