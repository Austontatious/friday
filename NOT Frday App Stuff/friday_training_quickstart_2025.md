# 🚀 FRIDAY Cloud Training – Quickstart (Verified 2025 Edition)

Here’s your no-nonsense, copy/paste-ready guide for next time you're feeling spicy with $20s and GPU dreams.

---

## ☁️ 1. Spin Up a Cloud VM
- **Recommended**: 8× H100, A100, or 4× A10G (budget version)
- **OS**: Ubuntu 20.04 or newer
- **Mount ephemeral drives**:
  ```bash
  /ephemeral/friday_data
  /ephemeral/friday_models
  /ephemeral/friday_database
  ```

---

## 🛠️ 2. Environment Setup
```bash
sudo apt update && sudo apt install -y python3.10 python3.10-venv git unzip tree
python3.10 -m venv friday_venv
source friday_venv/bin/activate
pip install --upgrade pip
pip install transformers datasets accelerate deepspeed peft
```

---

## 📁 3. Recommended Project Layout
```
/workspace/friday/
├── generate_curriculum_passes.py    # builds training_db.json and 3-pass sets
├── train_friday_autopilot.py        # fine-tunes via HuggingFace/Accelerate
├── models/        -> /ephemeral/friday_models
├── data/          -> /ephemeral/friday_data
├── output/        # stores checkpoints
├── training_db.json
```

Mount ephemeral drives with:
```bash
ln -s /ephemeral/friday_data /workspace/friday/data
ln -s /ephemeral/friday_models /workspace/friday/models
ln -s /ephemeral/friday_database /workspace/friday/database
```

---

## 🧠 4. Generate Your 3-Pass Curriculum
```bash
python3 /mnt/data/generate_curriculum_passes.py
```

It’ll create:
- `/workspace/friday/data/pass1.jsonl`
- `/workspace/friday/data/pass2.jsonl`
- `/workspace/friday/data/pass3.jsonl`
- `/workspace/friday/training_db.json`

---

## 🧬 5. Fine-Tuning
```bash
accelerate launch train_friday_autopilot.py
```

✅ Uses `training_db.json` to run each pass in sequence  
✅ Runs 1 epoch per pass (customizable)

---

## 💥 Common Pitfalls
| Issue | Fix |
|-------|-----|
| `No module named 'friday'` | Use flat imports or set `PYTHONPATH` |
| `ValueError: No valid training samples found` | Files missing or paths wrong in `training_db.json` |
| `CUDA out of memory` | Reduce `batch_size`, `max_length`, or number of GPUs |
| `tokenizer.pad()` fails | Use `DataCollatorWithPadding` from `transformers` |

---

## 🐢 6. Run on Your Local Laptop (~10h Strategy)

Your MSI Bravo 15 (6GB VRAM) can do this — just need to be gentle:

### 🔧 Recommended Adjustments:
```python
args = TrainingArguments(
    per_device_train_batch_size=1,
    num_train_epochs=1,
    gradient_accumulation_steps=8,  # simulate batch size of 8
    fp16=True,  # or bf16 if your GPU supports it
    max_steps=3000,  # cap to reduce runtime
    save_steps=1000,
    logging_steps=50,
    save_total_limit=1,
    ...
)
```

- Cap each pass to ~5,000 samples max
- Lower `max_length` to 1024
- Disable Deepspeed

### 🧪 How to start:
```bash
source friday_venv/bin/activate
python3 generate_curriculum_passes.py  # includes sample cap
accelerate config  # run interactively, use single-device
accelerate launch train_friday_autopilot.py
```
