import os
import torch
torch.backends.cuda.matmul.allow_tf32 = True
import subprocess
def clear_vram():
    try:
        subprocess.run("sudo fuser -v /dev/nvidia* | awk '/python/ {print $2}' | xargs -r sudo kill -9", shell=True, check=True)
        print("✅ VRAM cleared.")
    except subprocess.CalledProcessError:
        print("⚠️  VRAM clearing skipped or failed.")

clear_vram()

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

# 🔧 Memory optimization
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:32,expandable_segments:True"
os.environ["WANDB_DISABLED"] = "true"

BASE_PATH = "/mnt/storage/friday-fine-tune"
DATA_PATH = "/mnt/ai-lab/friday/data"
ADAPTER_PATH = os.path.join(BASE_PATH, "adapters")
os.makedirs(ADAPTER_PATH, exist_ok=True)

# 🧠 Define models and datasets
MODELS = [
    {
        "name": "openchat",
        "model_path": f"{BASE_PATH}/openchat/model",
        "dataset": f"{DATA_PATH}/oasst1.jsonl"
    },
    {
        "name": "deepseek",
        "model_path": f"{BASE_PATH}/deepseek/model",
        "dataset": f"{DATA_PATH}/code_alpaca.jsonl"
    }
]

for config in MODELS:
    print(f"\n🚀 Starting training for: {config['name']}")

    # 🧠 Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config["model_path"], trust_remote_code=True)

    # ⚙️ Choose quantization config
    if config["name"] == "openchat":
        quant_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True
        )
    else:
        quant_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
            llm_int8_skip_modules=None
        )

    # 🧠 Load model with quant config
    model = AutoModelForCausalLM.from_pretrained(
        config["model_path"],
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True
    )

    # 🧩 Prepare for training
    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()

    # 🧪 LoRA
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["qkv_proj", "o_proj", "gate_up_proj", "down_proj"]
    )
    model = get_peft_model(model, lora_config)

    # 📚 Load and tokenize dataset
    dataset = load_dataset("json", data_files=config["dataset"])["train"]

    def tokenize(example):
        tokens = tokenizer(
            example["text"],
            padding="max_length",
            truncation=True,
            max_length=512,
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = dataset.map(tokenize, batched=False)

    # 🧪 Data collator
    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )

    # 🏋️‍♂️ Training arguments
    training_args = TrainingArguments(
        output_dir=f"{ADAPTER_PATH}/{config['name']}-adapter",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=1,
        max_steps=150,
        save_steps=150,
        save_total_limit=1,
        logging_dir=f"{ADAPTER_PATH}/logs_{config['name']}",
        logging_steps=10,
        fp16=True,
        optim="adamw_torch",
        learning_rate=1e-4,
        warmup_steps=5,
        weight_decay=0.01,
        report_to="none"
    )

    # 🚀 Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        tokenizer=tokenizer,
        data_collator=collator
    )

    torch.cuda.empty_cache()
    trainer.train()
    print(f"✅ Training complete: {config['name']}")

