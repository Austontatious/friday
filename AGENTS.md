# AGENTS.md

This repo uses `/mnt/data/AGENTS_CORE.md` as the global contract.
Repo-specific overrides and invariants below.

## Repo-Specific Invariants
## Purpose
FRIDAY is a modular, multimodal personal digital assistant (Tony Stark-style), designed to run in multiple capability modes:
- Text-only
- Text + Voice (STT/TTS)
- Text + Voice + Vision (image + gesture)
- Full suite (voice, vision, gesture, real-time avatar render)

The system must degrade gracefully based on available compute and feature flags.

## Hard Rules (Safety + Repo Hygiene)
1. **Work only inside this repo** (no reading or modifying outside the FRIDAY repository tree).
2. **Single canonical paths only**:
   - `backend/` is canonical backend
   - `frontend/` is canonical frontend
   - `services/` is canonical model/service containers
   - Do not create duplicate “snapshot trees” (no `Friday/FRIDAY/` mirrors).
3. **Never break `make up`** (or the documented start command). If you must do large refactors, stage them behind flags.
4. **Every new feature must have a feature flag** (env-based). Default OFF unless required for baseline.
5. **Long-running work is async**: anything that can exceed ~2s must be a job with status polling or streaming.
6. **No “silent failures”**: return structured errors with `code`, `message`, `detail`, and `retryable`.
7. **Portability**: no hard-coded `/workspace/...` paths. Use env + relative paths.
8. **Observability**: all services must expose health endpoints; backend exposes `/healthz` and `/readyz`.

## What to Prefer
- Small, composable modules, explicit interfaces.
- Typed request/response schemas.
- Job queue pattern for multimodal tasks (audio transcription, vision, avatar frames).
- “Capability detection”: backend should report what is enabled and what is available.

## What to Avoid
- Duplicate routes for the same path.
- Multiple incompatible memory systems.
- Tool schemas that aren’t validated.
- Mixing frontend build systems (pick one: Vite preferred).
- Blocking calls in request handlers for model inference.

## Required Deliverables When Implementing Changes
- Update `PROJECT_MEMORY.md` with:
  - What changed
  - Why
  - New env flags
  - How to test
- Update docs under `docs/` if behavior changes.
- Add/adjust smoke tests where possible.

## Definition of Done (Per PR / Patch Set)
- Backend boots cleanly
- `/healthz` and `/readyz` work
- The mode matrix works (text-only at minimum)
- No duplicated routes, no invalid compose, no broken start scripts

<!-- BEGIN MUNINN CUTOVER GUARDRAILS (2026-02-16) -->
## Muninn Cutover Guardrails
- Muninn is integrated as an external HTTP service only. Do not vendor or copy Muninn source into FRIDAY.
- Memory provider selection is env-driven via `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none`.
- Default provider is `muninn`; fallback path must keep chat working when Muninn is unavailable.
- Use only canonical backend/frontend/service trees; no duplicate snapshot trees.
- Keep memory confirmation UX minimal until per-item selection is explicitly requested.
- Memory provider errors must be structured and logged; never fail the user turn silently.
<!-- END MUNINN CUTOVER GUARDRAILS -->

## Overrides
- GIT_POLICY: conservative
- Rationale: Default safety baseline; no local git-policy relaxation is required for routine work.

## Commit Discipline
- Commits must be small and scoped by default.
- If a change touches more than 10 files, the commit message body must explain why, or the change should be split into multiple commits (preferred).
- `.env` must never be committed; only `.env.example`-style templates may be committed.
