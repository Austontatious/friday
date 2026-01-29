# FRIDAY Migration Plan (Lexi-grade Upgrade)

## Phase 0 — Make it Run (Stabilization)
Goal: eliminate “can’t start” issues and unify sources of truth.

1) Entrypoint + routes
- Choose a single backend entrypoint (e.g. `backend/main.py`)
- Remove duplicate `/process` routes
- Ensure the frontend hits exactly one canonical API route

2) Compose validity
- Fix invalid docker-compose YAML (duplicate networks)
- Add healthchecks
- Ensure ports are documented and consistent

3) Tooling plumbing
- One tool registry + one executor
- One tool-call schema (JSON) with validation
- Remove broken signatures and registry typos
- Make “list tools” and “run tool” actually work

4) Memory consolidation
- Pick one MemoryManager API and align all call sites
- Ensure store/recall doesn’t crash
- Add safe no-op if persistence disabled

Deliverable:
- `docker compose up` works
- `/healthz` and `/readyz` work
- Text-only chat works end-to-end

---

## Phase 1 — Lexi Patterns (Identity + Tiered Memory + Jobs)
Goal: core “assistant continuity” and safe feature flags.

1) Identity
- Implement user_id resolution (device/session/handle)
- Store per-user memory buckets

2) Memory tiers
- Tier 0: ephemeral
- Tier 1: persisted JSONL
- Tier 2: optional vector store
All behind flags with safe defaults.

3) Async jobs
- Job table/store + status endpoints
- Convert any slow tasks to jobs (including tool calls if needed)

4) Emotion Lite
- Add optional conversation signals (sentiment/frustration/urgency)
- Use it only for tone + prioritization (no manipulation)

Deliverable:
- Two devices get two stable user_ids
- Memory persists across restarts when enabled
- Jobs work (create/status/result)

---

## Phase 2 — Multimodal Foundation (Voice + Vision + Gesture)
Goal: reliable media input/output with graceful degradation.

1) STT service
- Add STT container + API wrapper
- Streaming optional; async job always works

2) TTS service
- Add TTS container + voice selection + caching

3) Vision service
- Image upload endpoint
- Vision job: caption/objects + optional OCR

4) Gesture
- Start with CPU MediaPipe pipeline
- Provide events (hand position, pinch, select) to backend

Deliverable:
- Toggle matrix works: text-only / voice / voice+vision / etc.
- Frontend respects `/capabilities`

---

## Phase 3 — Real-time “Holographic” Avatar (Full Suite)
Goal: real-time, monochrome, ethereal, no-background avatar projection aesthetic.

1) Output target
- Transparent background frames (alpha)
- Monochrome shading + bloom/glow in post
- “Laser array / hologram” feel: scanlines + dithering + slight temporal shimmer

2) Pipeline strategy
- Real-time render path:
  - lightweight 3D/2.5D rig + shader effects (fast)
  - optional face/pose drive from camera
- High-end path:
  - neural avatar refinement as optional paid “polish” (jobs)

3) Transport
- WebRTC (ideal) or WebSocket frames (simpler)
- Keep fallback: static idle animation if bandwidth low

Deliverable:
- Avatar runs in real-time on supported GPU
- Degrades to simple animation on CPU
- No background always
