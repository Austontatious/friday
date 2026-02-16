# AGENTS.md — FRIDAY (Codex Operating Contract)

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

<!-- BEGIN CHAT-CODEX COORDINATION PROTOCOL -->

## Chat <-> Codex Coordination Protocol

**Purpose:**
This document establishes a simple coordination standard between the conversational planner (Chat) and the execution agent (Codex). It ensures instructions are interpretable, reproducible, and auditable across iterative development cycles.

### 1. Roles

**Chat (Planner / Architect)**
Responsible for:
- Translating user intent into structured execution plans
- Defining required inputs, expected outputs, and success criteria
- Providing environment assumptions and dependency expectations
- Interpreting results and deciding next steps

**Codex (Executor / Operator)**
Responsible for:
- Implementing the provided execution plan
- Running commands, scripts, or builds
- Capturing logs, outputs, metrics, and artifacts
- Reporting deviations, errors, or uncertainties

### 2. Instruction Format (Chat -> Codex)

Every execution instruction should contain:

**A. Objective**
Short statement of what must be accomplished.

**B. Environment Assumptions**
- Working directory
- Required services running (Docker, vLLM, DB, etc.)
- Hardware assumptions if relevant
- Required environment variables

**C. Execution Steps**
Numbered, deterministic commands or scripts.

**D. Expected Outputs**
- Files created
- Metrics produced
- Logs expected
- Artifacts saved

**E. Success Criteria**
Clear conditions indicating completion.

**F. Failure Handling**
What Codex should do if a step fails:
- Retry?
- Log and continue?
- Halt and report?

### 3. After-Action Report Format (Codex -> Chat)

Codex should respond with the following structure:

**A. Execution Summary**
- Objective attempted
- Start / end time
- Environment used

**B. Steps Performed**
Numbered list of executed steps (exact commands preferred).

**C. Outputs Generated**
- Files created
- Metrics
- Artifacts

**D. Errors or Deviations**
- Any failures
- Unexpected results
- Missing dependencies

**E. Verification**
State whether success criteria were met:
- Fully met
- Partially met
- Not met

**F. Next-Step Recommendations (Optional)**
Observations that may influence the next iteration.

### 4. Alignment Rules

1. Codex must not improvise architectural decisions unless explicitly instructed.
2. Chat must provide deterministic steps whenever reproducibility is required.
3. All training, dataset, or model runs must record:
- Dataset identifier / hash
- Checkpoint path
- Config used
- Metrics output location
4. If any instruction is ambiguous, Codex should ask for clarification before executing destructive actions.
5. All long-running processes must log to a persistent run directory.

### 5. Standard Run Directory Structure

```txt
artifacts/
  runs/
    <timestamp>_<run_name>/
      config.yaml
      stdout.log
      stderr.log
      metrics.json
      checkpoints/
      notes.txt
```

### 6. Communication Shortcuts

When Chat sends instructions, the message should begin with:

```txt
CODEX EXECUTION SHEET
```

When Codex replies, the message should begin with:

```txt
CODEX AFTER ACTION REPORT
```

This allows rapid scanning and prevents instruction/result confusion.

### 7. Iteration Loop

1. User describes goal
2. Chat produces Execution Sheet
3. Codex executes
4. Codex returns After-Action Report
5. Chat analyzes results
6. Next Execution Sheet generated

Repeat until success criteria are satisfied.

### 8. Priority Principle

Correctness > Reproducibility > Speed

If a tradeoff must be made, preserve correctness and full logging first.

### 9. Minimal Execution Sheet Template

```txt
CODEX EXECUTION SHEET

Objective:
Environment Assumptions:
Execution Steps:
Expected Outputs:
Success Criteria:
Failure Handling:
```

### 10. Minimal After-Action Template

```txt
CODEX AFTER ACTION REPORT

Execution Summary:
Steps Performed:
Outputs Generated:
Errors / Deviations:
Verification:
Next-Step Notes:
```

End of Protocol

<!-- END CHAT-CODEX COORDINATION PROTOCOL -->

<!-- BEGIN MUNINN CUTOVER GUARDRAILS (2026-02-16) -->
## Muninn Cutover Guardrails
- Muninn is integrated as an external HTTP service only. Do not vendor or copy Muninn source into FRIDAY.
- Memory provider selection is env-driven via `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none`.
- Default provider is `muninn`; fallback path must keep chat working when Muninn is unavailable.
- Use only canonical backend/frontend/service trees; no duplicate snapshot trees.
- Keep memory confirmation UX minimal until per-item selection is explicitly requested.
- Memory provider errors must be structured and logged; never fail the user turn silently.
<!-- END MUNINN CUTOVER GUARDRAILS -->
