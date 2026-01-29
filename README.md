# FRIDAY (Phase 0 — Make It Run)

FRIDAY is a modular assistant. Phase 0 is **text-only** and focuses on a stable, runnable spine.

## What works (Phase 0)
- Text chat (single `/api/chat` route)
- Health endpoints (`/healthz`, `/readyz`)
- Single backend entrypoint (`backend/main.py`)
- One memory system (ephemeral)
- One tool system (minimal registry, not wired to LLM yet)

## What is disabled (Phase 0)
- Multimodal (STT/TTS/Vision/Gesture/Avatar)
- Emotion features
- Persistent/vector memory

## Quick Start (backend only)
```bash
cp .env.example .env
docker compose up --build
```

Backend runs on `http://localhost:9001` by default.

## API
- `POST /api/chat` — body: `{ "prompt": "..." }`
- `GET /healthz`
- `GET /readyz`

Example:
```bash
curl -s http://localhost:9001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Hello FRIDAY"}'
```

## Frontend (optional for Phase 0)
```bash
cd frontend
npm install
npm start
```
Set `REACT_APP_API_URL=http://localhost:9001/api` if you want a custom API target.

## Notes
- LLM configuration is via env:
  - `FRIDAY_LLM_ENABLED=1`
  - `FRIDAY_MODEL_PATH=/path/to/model.gguf` **or** `LLM_BASE_URL=http://host:port`
  - `FRIDAY_MODEL_NAME=friday` (for remote OpenAI-compatible servers)
