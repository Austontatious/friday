import os
import torch

# Define VRAM limits (in MB)
VRAM_LIMITS = {
    "deepseek-coder": 4000,  # 4GB for DeepSeek
    "phi-3": 4000,           # 4GB for Phi-3
    "mixtral": 6000,         # 6GB for Mixtral
}

# Define model paths and names
models = {
    "deepseek-coder": "/mnt/dev-models/deepseek-coder/deepseek-coder-6.7b-instruct-q4_k_m.gguf",
    "phi-3": "/mnt/dev-models/phi-3/phi-3-mini-4k-instruct-q5_k_m.gguf",  # Updated Phi-3 model
    "mixtral": "/mnt/dev-models/mixtral/mixtral-8x7b-v0.1.Q3_K_M.gguf",  # Updated Mixtral model
}

def check_vram(model_name):
    """Check if there is enough VRAM available for the selected model and calculate shortfall."""
    available_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)  # in MB
    required_vram = VRAM_LIMITS.get(model_name, 0)
    
    print(f"Available VRAM: {available_vram}MB")
    print(f"Required VRAM for {model_name}: {required_vram}MB")
    
    if available_vram < required_vram:
        shortfall = required_vram - available_vram
        print(f"❌ Short by {shortfall}MB for {model_name}.")
        return False
    else:
        return True

def model_status():
    """Check and display status of each model."""
    for model, model_path in models.items():
        file_size = os.path.getsize(model_path) / (1024 * 1024)  # Size in MB
        print(f"{model}: {file_size}MB")
        status = check_vram(model)
        if status:
            print(f"✅ {model} fits in VRAM.")
        else:
            print(f"❌ {model} does NOT fit in VRAM.")

if __name__ == "__main__":
    model_status()

