# FRIDAY Architecture

## High-Level Components
1. **Gateway Backend (FastAPI)**
   - Routes: chat, tools, jobs, upload endpoints
   - Identity resolution
   - Memory orchestration
   - Capability reporting
   - Health checks

2. **Model/Media Services (Dockerized, optional)**
   - LLM service (vLLM or local server)
   - STT service (faster-whisper or whisper.cpp)
   - TTS service (XTTS/OpenVoice/Piper-style)
   - Vision service (Qwen2-VL / Florence / etc.)
   - Gesture service (MediaPipe / local inference)
   - Avatar render service (real-time frames; GPU optional)

3. **Worker / Queue**
   - For async jobs: STT, vision, avatar frames, indexing
   - Simple: Redis queue or in-proc queue for dev

4. **Frontend**
   - Single build system (Vite preferred)
   - Supports: text chat always; voice/vision/gesture UI if enabled
   - Polling/streaming UX for jobs

## Key Concepts
### Capability Matrix
Backend exposes `/capabilities`:
- What is enabled by env
- What is actually reachable/healthy
Frontend uses it to show/hide UI.

### Identity
Stable user id derived from:
- device_id (preferred)
- session_id
- optional handle/email
Disambiguation flow if collisions. All memory hangs off user_id.
Workspace isolation is keyed by `workspace_id` (default `default`).

### Memory Tiers
- Tier 0: session context (in-memory)
- Tier 1: persisted JSONL threads + facts/preferences + episodic summaries
- Tier 2 (optional): vector store / embeddings
All tiers feature-flagged and safe to disable.

### Interaction Policy (Rule-Based v1)
- Deterministic mode inference: `focused | neutral | warm`.
- Signals: urgency terms, profanity/caps, short imperative commands, repeated corrections, recent tool-failure loops.
- Explicit user overrides: `be brief`, `be human`, `no banter`.
- `playful` exists but is hard-gated (`FRIDAY_INTERACTION_PLAYFUL_ENABLED=1` + explicit user request).
- Prompt receives an `<INTERACTION_POLICY>` block, then a deterministic response shaper enforces:
  - banter budget
  - one-question cap
  - one-screen default with optional details expansion

### Async Jobs
All inference that can exceed ~2s becomes:
- POST /jobs (create)
- GET /jobs/{id} (status)
- GET /jobs/{id}/result (result)
Optionally WebSocket for streaming.

### Trust Boundary
Inputs are classified as trusted user, untrusted channel, or untrusted document.
Untrusted content may influence answers but cannot trigger tools without confirmation.

## Data Flow (Typical)
User → Frontend → Backend `/chat`
Backend:
- resolves user_id
- loads memory tiers (as enabled)
- runs tool planner (LLM)
- executes tools (if any)
- returns streaming tokens or final response
If vision/audio/avatar requested: create job, return job_id, frontend polls.

## Agentic Run API (Async)
- `POST /api/agent` accepts a run and returns `{run_id, status:"accepted"}` immediately.
- `POST /api/agent/wait` waits on lifecycle completion and returns `ok|error|timeout`.
- Runs are serialized per session key with global lane concurrency caps.
