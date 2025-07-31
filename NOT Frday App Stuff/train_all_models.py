import os
import torch
import subprocess
import json
import time
import traceback
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

# ✅ TF32 optimization for speed
torch.backends.cuda.matmul.allow_tf32 = True
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:32,expandable_segments:True"
os.environ["WANDB_DISABLED"] = "true"

BASE_PATH = "/mnt/storage/friday-fine-tune"
DATA_PATH = "/mnt/ai-lab/friday/data"
ADAPTER_PATH = os.path.join(BASE_PATH, "adapters")
os.makedirs(ADAPTER_PATH, exist_ok=True)

# 🧠 MODEL CONFIGURATIONS
MODELS = {
    "openchat": {
        "path": f"{BASE_PATH}/openchat/model",
        "dataset": f"{DATA_PATH}/oasst1.jsonl",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "down_proj", "up_proj"]
    },
    "deepseek": {
        "path": f"{BASE_PATH}/deepseek/model",
        "dataset": f"{DATA_PATH}/code_alpaca.jsonl",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "down_proj", "up_proj"]
    },
    "mixtral": {
        "path": f"{BASE_PATH}/mixtral/model",
        "dataset": f"{DATA_PATH}/oasst1.jsonl",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "down_proj", "up_proj"]
    }
}

# 🧪 PROFILE DEFINITIONS
PROFILES = [
    {
        "name": "safe",
        "max_length": 512,
        "batch_size": 1,
        "gradient_accumulation": 8,
        "fp16": True,
        "bf16": False,
        "use_cpu_offload": False
    },
    {
        "name": "light_4bit",
        "max_length": 256,
        "batch_size": 1,
        "gradient_accumulation": 16,
        "fp16": True,
        "bf16": False,
        "use_cpu_offload": False
    },
    {
        "name": "cpu_offload",
        "max_length": 128,
        "batch_size": 1,
        "gradient_accumulation": 16,
        "fp16": True,
        "bf16": False,
        "use_cpu_offload": True
    },
    {
        "name": "bf16_aggressive",
        "max_length": 512,
        "batch_size": 1,
        "gradient_accumulation": 4,
        "fp16": False,
        "bf16": True,
        "use_cpu_offload": False
    }
]

# 🔧 UTILITY FUNCTIONS
def clear_vram():
    try:
        subprocess.run("sudo fuser -v /dev/nvidia* | awk '/python/ {print $2}' | xargs -r sudo kill -9", shell=True, check=True)
        print("✅ VRAM cleared.")
    except subprocess.CalledProcessError:
        print("⚠️  VRAM clearing skipped or failed.")

def log_event(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def load_jsonl(path):
    with open(path, "r") as f:
        return [{"text": json.loads(line)["text"]} for line in f]

def run_training(model_name, model_config):
    for profile in PROFILES:
        log_event(f"\n🚀 Training model: {model_name}\n\n🔬 Trying profile: {profile['name']}")
        for attempt in range(1, 4):
            log_event(f"⚙️ Pass {attempt} for {model_name} using {profile['name']}")
            clear_vram()
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_config["path"])
                tokenizer.pad_token = tokenizer.eos_token
                dataset = load_jsonl(model_config["dataset"])
                tokenized = tokenizer([d["text"] for d in dataset], truncation=True, padding="max_length", max_length=profile["max_length"])

                config = BitsAndBytesConfig(load_in_8bit=True, llm_int8_enable_fp32_cpu_offload=profile["use_cpu_offload"])
                model = AutoModelForCausalLM.from_pretrained(
                    model_config["path"],
                    quantization_config=config,
                    device_map="auto"
                )

                model = prepare_model_for_kbit_training(model)
                lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=model_config["target_modules"], lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
                model = get_peft_model(model, lora_config)

                args = TrainingArguments(
                    output_dir=os.path.join(ADAPTER_PATH, f"{model_name}-adapter-{profile['name']}-run{attempt}"),
                    per_device_train_batch_size=profile["batch_size"],
                    gradient_accumulation_steps=profile["gradient_accumulation"],
                    num_train_epochs=1,
                    logging_steps=10,
                    save_strategy="no",
                    fp16=profile["fp16"],
                    bf16=profile["bf16"],
                    learning_rate=1e-4
                )
                trainer = Trainer(
                    model=model,
                    tokenizer=tokenizer,
                    args=args,
                    train_dataset=tokenized,
                    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
                )

                trainer.train()
                log_event(f"✅ Training complete for {model_name} in profile {profile['name']} on pass {attempt}")
                return
            except Exception as e:
                log_event(f"❌ Failed pass {attempt} for {model_name} in profile {profile['name']}: {str(e)}")
                traceback.print_exc()

for model_name, model_config in MODELS.items():
    run_training(model_name, model_config)

