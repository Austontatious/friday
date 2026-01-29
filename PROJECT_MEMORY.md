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
- Added `/api/capabilities` endpoint and shared health-check helpers
- Expanded backend compose env to pass capability flags + service URLs into the container
- Why: allow frontend gating and make enabled/available reporting consistent with env config
- Flags added/changed: none (existing flags now propagated into container)
- How to test: `curl http://localhost:9001/api/capabilities`
- Known issues: gesture/vector availability are reported as false (stubbed)

- Added in-proc jobs store with `/api/jobs` create/status/result endpoints
- /readyz now reports jobs backend status (memory or redis)
- Why: establish async job pattern before multimodal work
- Flags added/changed: none
- How to test: `curl -X POST http://localhost:9001/api/jobs -H 'Content-Type: application/json' -d '{}'`
- Known issues: jobs are queued-only (no worker yet)

- Upgraded memory to tiered store (T0 in-memory + optional T1 JSONL persistence) with vector stub
- /readyz now verifies persistence directory is writable when memory persistence is enabled
- Why: keep Phase 1 memory reliable while adding persistence behind FRIDAY_MEMORY_PERSIST_ENABLED
- Flags added/changed: none
- How to test: set `FRIDAY_MEMORY_PERSIST_ENABLED=1`, start backend, then `curl http://localhost:9001/readyz`
- Known issues: vector tier is stubbed (no-op)

- Added identity middleware to assign stable `user_id` via header/cookie and attach `X-Friday-User` response header
- Updated `/api/chat` to carry request `user_id` and return a friendly LLM-disabled response (HTTP 200)
- Why: establish stable identity buckets and keep text-only chat usable while LLM is disabled
- Flags added/changed: none
- How to test: start backend, then `curl -i -X POST http://localhost:9001/api/chat -H 'Content-Type: application/json' -d '{"prompt":"Hello"}'`
- Known issues: none

- Replaced `.env` with Phase 0 defaults (LLM disabled) and archived `.env` -> `.env.legacy`
- Rewired model profiles to service names `llm`, `stt`, `tts`, `vision`, `avatar` in `docker-compose.models.yml`
- Updated `.env.models.example` to minimal opt-in toggles
- Updated `/readyz` service keys to match URL env names (LLM_BASE_URL, STT_BASE_URL, etc.)
- Why: keep Phase 0 runnable while wiring optional models behind profiles
- Flags added/changed: FRIDAY_LLM_ENABLED default set to 0 in `.env.example`
- How to test: `docker compose -f docker-compose.yaml -f docker-compose.models.yml config > /tmp/compose.merged.yml`
- Known issues: none (models remain opt-in)

- Normalized service health probes to use `/v1/models` when base URLs end in `/v1`

- Added model compose wiring files: `docker-compose.models.yml`, `.env.models.example`
- Updated `/readyz` to report per-service status and honor *_ENABLED flags
- Updated chat error mapping to return `llm_unhealthy` when a configured LLM is unreachable
- Why: wire optional model services behind profiles without auto-start
- Flags added/changed: FRIDAY_CODER_ENABLED, FRIDAY_VISION_ENABLED, FRIDAY_OMNI_ENABLED, FRIDAY_STT_ENABLED, FRIDAY_TTS_ENABLED
- How to test: `docker compose -f docker-compose.yaml -f docker-compose.models.yml config > /tmp/compose.merged.yml`
- Known issues: none (models remain opt-in)

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
