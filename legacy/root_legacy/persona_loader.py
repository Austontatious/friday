from friday.persona import PersonaManager
from friday.memory.memory_core import MemoryManager
from friday.model_loader_core import initialize_model_loader
from friday.model_config import ModelType

# 🔁 Shared model loader
model_loader = initialize_model_loader()

# 🧠 Memory system (wired to ./memory_logs/default.jsonl)
from friday.memory.memory_store_json import MemoryStoreJSON

store = MemoryStoreJSON(filepath="/workspace/ai-lab/memory_logs/default.jsonl")
memory = MemoryManager(store)



# 👤 Persona instance with memory enabled
persona = PersonaManager(memory_manager=memory)

# ✅ Explicitly load the FRIDAY model
try:
    print("🔄 Attempting to load Friday model (shared)...")
    persona.load_model(ModelType.FRIDAY)
    print("✅ Friday model loaded successfully (shared).")
except Exception as e:
    print(f"❌ Failed to load Friday model in persona_loader: {e}")

