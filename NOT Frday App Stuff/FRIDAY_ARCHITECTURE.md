# FRIDAY\_ARCHITECTURE.md

## 🧠 Overview

FRIDAY is a local-first AI assistant that intelligently routes user input to the most appropriate model, leveraging quantized GGUF backends via `llama.cpp`. It includes memory, persona management, model monitoring, and a Chakra-powered frontend. It is designed for immediate responsiveness, task awareness, and extensibility.

---

## ⚙️ Core Backend Components

### `server.py`

* Main FastAPI app
* Sets up middleware, CORS, logging
* Runs model monitoring and launches routers

### `routes/`

* `friday_routes.py`: POST `/process`, health check, monitor, capabilities
* `code_routes.py`: Endpoint wiring for code-based tasks

### `task_manager.py`

* Classifies tasks (`TaskType`) and assigns appropriate model
* Injects relevant memory context and persona formatting

### `persona.py`

* Handles template-based prompt generation
* Chooses `j2` template per model (e.g., `openchat_chat.j2`)
* Integrates memory into response pipeline

### `model_loader_core.py`

* Loads quantized GGUF models with `llama.cpp`
* Handles batching, max context, LoRA patches

### `model_config.py`

* Registry of model paths, context length, temperature, GPU layer counts

### `model_types.py`

* Enums for `ModelType`, `TaskType`, `ModelStatus`
* Routing logic for fallback behavior

### `memory.py`

* Embeds and stores interaction vectors
* ChromaDB interface (default), FAISS supported

### `context.py`

* FastAPI endpoints for memory:

  * `POST /context/store`
  * `GET /context/retrieve`
  * `POST /context/clear`

### `model_monitor.py`

* Logs GPU/memory use, latency, errors
* Supports Prometheus metrics if enabled

### `response_formatter.py`

* Final output cleanup for frontend consumption

---

## 🎨 Frontend Architecture

### Stack

* React (Vite), Chakra UI 2.x, Tailwind CSS
* Project root: `/friday/frontend/`

### Main Structure

* `src/`

  * `App.tsx`: Entry point, renders `ThoughtWindow`, `ChatHistory`
  * `services/api.ts`: Handles `/process` requests and capabilities fetch
  * `components/`: UI elements and interaction components
* `vite.config.ts`: Vite build system
* `tailwind.config.js`: Theme overrides
* `Friday theme.txt`: UX and palette references

---

## 🔁 System Flow

```
User Input
  ↓
React Frontend (/process) → FastAPI Router
  ↓
TaskManager → Persona → ModelLoader
  ↓
Model Inference (llama.cpp)
  ↓
Result Formatting → Memory Storage
  ↓
Frontend Response
```

---

## 🧬 Model Registry

```python
MODEL_REGISTRY = {
    "openchat": "/models/openchat-7b.Q4_K_M.gguf",
    "mixtral": "/models/mixtral-8x7b-v0.1.Q3_K_M.gguf",
    "deepseek": "/models/deepseek-coder-6.7b.Q4_K_M.gguf"
}
```

## Model Config Defaults

| Model    | Context | GPU Layers | Temp | Top-p |
| -------- | ------- | ---------- | ---- | ----- |
| OpenChat | 4096    | 35         | 0.3  | 0.95  |
| Mixtral  | 4096    | 33         | 0.6  | 0.95  |
| DeepSeek | 4096    | 35         | 0.7  | 1.0   |

---

## 🔒 Security + Optimization

* Context length capped at 4096 to reduce KV cache
* Models unloaded after inference unless pinned
* Automatic fallback to OpenChat when task type is unclear
* Token streaming supported but disabled by default
* GPU detection and dynamic layer mapping at startup

---

## ✅ Current Capabilities

* Multi-model routing
* Memory retrieval (ChromaDB)
* Local quantized inference (GGUF)
* Prometheus-compatible metrics
* React-based UI with real-time thought display
* Configurable persona templates per model

---

## 🧩 Future Improvements

* Context window expansion to 16k for Mixtral
* Optional persistent memory snapshots
* Frontend user settings panel
* Richer persona editor with live test
* Background preloading/warmup of models

---

Generated May 2, 2025

