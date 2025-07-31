from datasets import load_dataset

print("📦 Downloading datasets...")

# Phi-3 / Chat fine-tuning
oasst = load_dataset("OpenAssistant/oasst1", split="train[:5000]")
oasst.to_json("/mnt/ai-lab/friday/data/oasst1.jsonl")

# DeepSeek / Code fine-tuning (FIXED)
code = load_dataset("HuggingFaceH4/CodeAlpaca_20K", split="train[:5000]")
code.to_json("/mnt/ai-lab/friday/data/code_alpaca.jsonl")

# Mixtral / Reasoning & QA
orca = load_dataset("Open-Orca/OpenOrca", split="train[:5000]")
orca.to_json("/mnt/ai-lab/friday/data/open_orca.jsonl")

print("✅ All datasets saved in /mnt/ai-lab/friday/data/")

