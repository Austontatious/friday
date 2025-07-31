# FRIDAY\_OVERVIEW\.md

## 🧠 What is FRIDAY?

**FRIDAY** is a self-hosted, intelligent assistant that runs entirely on local hardware. Built for performance and privacy, FRIDAY dynamically routes tasks between multiple specialized open-source models like OpenChat, Mixtral, and DeepSeek. Its architecture combines GPU-accelerated inference, vector memory, and a real-time React frontend.

---

## 🔧 Backend Core

### FastAPI Server

* Defined in `server.py`
* Launches model services and routes
* Integrates CORS, logging, lifecycle hooks

### Key Modules

* `task_manager.py`: Routes tasks to models based on type
* `persona.py`: Formats prompts using templates per model
* `model_loader_core.py`: Loads GGUF models via `llama.cpp`
* `model_config.py`: Defines temperature, path, and context length
* `context.py`: FastAPI routes for storing/retrieving memory
* `memory.py`: ChromaDB interface for semantic retrieval

---

## 🎨 Frontend Core

### Built With:

* React + Vite
* Chakra UI + Tailwind CSS

### Structure:

* `src/App.tsx`: Main entry
* `services/api.ts`: Connects to `/process` endpoint
* `components/`: UI modules like `ThoughtWindow`, `ChatHistory`

### Design Highlights:

* "ThoughtWindow" shows real-time model thoughts
* Full chat history with formatting, avatars, role tags
* Light/dark themes supported (toggle in progress)

---

## 🤖 Models Supported

| Model    | Use Case                      | Config Path                               |
| -------- | ----------------------------- | ----------------------------------------- |
| OpenChat | General chat & assistant work | `/models/openchat-7b.Q4_K_M.gguf`         |
| Mixtral  | Logic, reasoning, CoT         | `/models/mixtral-8x7b-v0.1.Q3_K_M.gguf`   |
| DeepSeek | Code completion & generation  | `/models/deepseek-coder-6.7b.Q4_K_M.gguf` |

Routing is managed by `task_manager.py`, with fallbacks to OpenChat for ambiguous tasks.

---

## 🔁 Request Lifecycle

```
User Input
  ↓
React Frontend (/process) → FastAPI Backend
  ↓
Task Classification → Model Selection
  ↓
Prompt Generation → Inference
  ↓
Memory Storage → Frontend Response
```

---

## 📦 Model Settings (Default)

| Model    | Context | GPU Layers | Temp | Top-p |
| -------- | ------- | ---------- | ---- | ----- |
| OpenChat | 4096    | 35         | 0.3  | 0.95  |
| Mixtral  | 4096    | 33         | 0.6  | 0.95  |
| DeepSeek | 4096    | 35         | 0.7  | 1.0   |

All values can be overridden in `model_config.py`.

---

## 🔐 Security & Optimization

* GPU usage optimized via dynamic layer mapping
* Context capped at 4096 to limit KV cache
* Models are unloaded post-inference unless pinned
* Prometheus metrics supported
* Error recovery via `error_handler.py`

---

## ✅ Features Checklist

* [x] Multi-model routing (code/chat/logic)
* [x] FastAPI backend + React frontend
* [x] Memory vector store with Chroma
* [x] Real-time UI with Chakra and Tailwind
* [x] Streaming-friendly prompt-response loop

---

## 🔮 Roadmap

* Expand Mixtral context to 16k
* Add GUI for persona management
* Memory snapshot + long-term recall
* Add multi-user sessions and identity tracking
* Dark/light theme switching and UI polish

---

Generated May 2, 2025

