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

### Memory Tiers
- Tier 0: session context (in-memory)
- Tier 1: persisted JSONL thread + facts
- Tier 2 (optional): vector store / embeddings
All tiers feature-flagged and safe to disable.

### Emotional Awareness (Lite)
Track *non-manipulative* signals:
- sentiment / arousal / frustration (coarse)
- conversation “temperature”
- user preferences / intent drift
Used only to improve tone, prioritization, and clarity.

### Async Jobs
All inference that can exceed ~2s becomes:
- POST /jobs (create)
- GET /jobs/{id} (status)
- GET /jobs/{id}/result (result)
Optionally WebSocket for streaming.

## Data Flow (Typical)
User → Frontend → Backend `/chat`
Backend:
- resolves user_id
- loads memory tiers (as enabled)
- runs tool planner (LLM)
- executes tools (if any)
- returns streaming tokens or final response
If vision/audio/avatar requested: create job, return job_id, frontend polls.
