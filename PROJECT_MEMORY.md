# FRIDAY Project Memory (Codex Read/Write)

## How to use this file
- This is the canonical running memory for the repo.
- Every patch set must append a short entry under "Change Log".
- Keep it factual: what changed, where, why, how to test, and any new flags.

---

## Current Target
Upgrade FRIDAY to Lexi-grade architecture patterns + modern multimodal capabilities:
- tiered memory
- identity binding
- async jobs
- capability flags
- multi-container services
- holographic monochrome avatar render (no background)

## Non-negotiables
- Text-only mode must always run.
- Everything else is optional and feature-flagged.
- No hardcoded paths. No duplicate trees.
- All long-running tasks async/streamed.

## Open Decisions
- Queue choice: Redis/RQ vs Celery vs lightweight in-proc (dev)
- TTS choice: XTTS vs Piper vs OpenVoice
- Vision choice: Qwen2-VL vs Florence vs other
- Gesture: MediaPipe (CPU) vs GPU model

## Capability Flags (planned)
- FRIDAY_LLM_ENABLED
- FRIDAY_STT_ENABLED
- FRIDAY_TTS_ENABLED
- FRIDAY_VISION_ENABLED
- FRIDAY_GESTURE_ENABLED
- FRIDAY_AVATAR_ENABLED
- FRIDAY_MEMORY_PERSIST_ENABLED
- FRIDAY_MEMORY_VECTOR_ENABLED
- FRIDAY_EMOTION_LITE_ENABLED
- FRIDAY_JOBS_ENABLED

## Change Log
### 2026-01-29
- Added `tools/pull_models.sh` model fetcher (HF + GitHub) with manifest output
- Why: standardize model pulls and repos for Phase 1 multimodal stack
- Flags added/changed: none
- How to test: `HF_TOKEN=... ./tools/pull_models.sh`
- Known issues: script exits if HF_TOKEN is not set

- Phase 0 stabilization: added canonical backend spine under `backend/` (entrypoint, chat, health, memory, tools)
- Deprecated legacy routes/entrypoints and removed duplicate `/process` handlers in active paths
- Fixed `start.sh`, `process_manager.py`, `Dockerfile`, `docker-compose.yaml` for a single runnable backend
- Updated frontend API wiring to `/api/chat` with flat `{text}` response
- Moved legacy memory/tools/routes/root modules to `legacy/` to enforce single systems
- Why: make docker compose run and establish a single, correct execution path
- Flags added/changed: FRIDAY_MEMORY_PERSIST_ENABLED defaulted to 0 in `.env.example`
- How to test: `docker compose up --build`, then `curl http://localhost:9001/healthz` and `curl -X POST http://localhost:9001/api/chat -H 'Content-Type: application/json' -d '{"prompt":"Hello"}'`
- Known issues: LLM requires `FRIDAY_MODEL_PATH` or `LLM_BASE_URL` to return non-error text

- Added operating contract and architecture docs: `AGENTS.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `docs/MIGRATION_PLAN.md`
- Added initial project memory ledger and documented planned capability flags
- Why: establish repo rules + target architecture + migration plan before code stabilization
- Flags added/changed: none (documented planned flags only)
- How to test: N/A (docs-only change)
- Known issues: N/A
