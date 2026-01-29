import os
import glob

def gather_files():
    """Gather all Python files and write them to a single file."""
    output_file = "FRIDAY_FULL_CODE.txt"
    files_to_gather = [
        "friday.py",
        "context.py",
        "memory.py",
        "persona.py",
        "models_config.py",
        "model_types.py",
        "model_loader.py",
        "model_loader_core.py",
        "model_monitor.py",
        "friday_routes.py",
        "task_manager.py",
        "error_handler.py",
        "rate_limiter.py",
        "template_loader.py",
        "server.py",
        "friday_test.py",
        "tests/test_memory.py",
        "tests/test_model_switching.py",
        "tests/__init__.py",
        "start.sh",
        "check-files.sh",
        "patch_files.py",
        "train_all_models.py",
        "download_datasets.py",
        "requirements.txt",
        "README.md",
        ".env.example",
        ".env"
    ]
    
    with open(output_file, "w") as outfile:
        for file_path in files_to_gather:
            if os.path.exists(file_path):
                outfile.write(f"\n{'='*80}\n")
                outfile.write(f"File: {file_path}\n")
                outfile.write(f"{'='*80}\n\n")
                with open(file_path, "r") as infile:
                    outfile.write(infile.read())
                outfile.write("\n\n")
            else:
                outfile.write(f"\n{'='*80}\n")
                outfile.write(f"File not found: {file_path}\n")
                outfile.write(f"{'='*80}\n\n")

if __name__ == "__main__":
    gather_files() 