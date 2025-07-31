from huggingface_hub import hf_hub_download
import os

models = {
    "deepseek-coder": {
        "repo": "anzuo/deepseek-coder-6.7b-instruct-Q4_K_M-GGUF",
        "filename": "deepseek-coder-6.7b-instruct-q4_k_m.gguf"
    },
    "phi-3": {
        "repo": "PrunaAI/microsoft-Phi-3-mini-4k-instruct-GGUF-smashed",
        "filename": "Phi-3-mini-4k-instruct.Q4_K_M.gguf"
    },
    "mixtral": {
        "repo": "TheBloke/Mixtral-8x7B-v0.1-GGUF",
        "filename": "mixtral-8x7b-v0.1.Q4_K_M.gguf"
    }
}

BASE_DIR = "/mnt/dev-models"

for name, model in models.items():
    folder = os.path.join(BASE_DIR, name)
    os.makedirs(folder, exist_ok=True)
    print(f"⬇️  Downloading {model['filename']} to {folder}...")

    try:
        file_path = hf_hub_download(
            repo_id=model['repo'],
            filename=model['filename'],
            local_dir=folder
        )
        print(f"✅ Successfully downloaded {model['filename']} to {file_path}")
    except Exception as e:
        print(f"❌ Failed to download {model['filename']}: {e}")

