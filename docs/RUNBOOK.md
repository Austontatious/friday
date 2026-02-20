# FRIDAY Runbook

## Quick Start
1. `cp .env.example .env`
2. If enabling LLM outside compose, set:
   - `FRIDAY_MODEL_NAME=Lexi`
   - `LLM_BASE_URL=http://127.0.0.1:8008`
   - optional interaction tuning:
     - `FRIDAY_INTERACTION_DEFAULT_MODE=neutral`
     - `FRIDAY_INTERACTION_ONE_SCREEN_CHARS=900`
     - `FRIDAY_INTERACTION_PLAYFUL_ENABLED=0`
3. `docker compose up --build`
4. Verify:
   - `curl -fsS http://localhost:9001/healthz`
   - `curl -fsS http://localhost:9001/readyz`
   - `curl -fsS http://localhost:8000/health`

## Memory Provider Modes
- `FRIDAY_MEMORY_PROVIDER=muninn` (default)
- `FRIDAY_MEMORY_PROVIDER=legacy`
- `FRIDAY_MEMORY_PROVIDER=none`

Muninn path is resilient by design:
- if Muninn request fails, FRIDAY logs warning + falls back (`legacy` or `none`)
- chat runtime continues and returns `assistant_text`

## Automated Smoke
```bash
bash scripts/smoke_memory.sh
```

Smoke checks:
1. Muninn health endpoint.
2. Chat response includes `memory.provider`.
3. Pending confirmation route path (`/api/memory/confirm`).
4. Post-confirm chat still returns memory metadata.
5. Isolated fallback run with unreachable Muninn URL still responds.

## Manual Smoke Checklist
1. Muninn up:
   - `curl -fsS http://localhost:8000/health`
2. FRIDAY up:
   - `curl -fsS http://localhost:9001/healthz`
3. Chat round-trip:
   - send prompt through `/api/chat`
   - verify response contains `memory.provider`
4. Rehydrate injection visibility (debug):
   - set `FRIDAY_DEBUG_MEMORY=1`
   - send chat turn
   - verify backend logs contain injected `<SYSTEM_MEMORY>` block (truncated)
5. Prompt assembly visibility (dev debug):
   - set `FRIDAY_DEBUG_PROMPT=1`
   - optional: `FRIDAY_DEBUG_PROMPT_MAX_CHARS=2000`
   - send chat turn
   - verify logs include `prompt_debug` with prompt length, head/tail excerpts, and memory append metadata
6. Confirm flow:
   - create pending ids (normal flow or staged test candidate)
   - UI banner appears ("X memories need confirmation")
   - `Accept all` calls `/api/memory/confirm`
   - next chat still returns memory metadata
7. Muninn down fallback:
   - stop `muninn` container
   - send chat request
   - verify FRIDAY still responds and `memory.provider` reflects fallback (`legacy` or `none`)

## Agentic API Quick Check
1. Submit async run:
   - `curl -fsS http://localhost:9001/api/agent -H 'Content-Type: application/json' -H 'X-Friday-Device: smoke-agent' -d '{"prompt":"Summarize this architecture","idempotency_key":"smoke-agent-1"}'`
2. Wait for completion:
   - `curl -fsS http://localhost:9001/api/agent/wait -H 'Content-Type: application/json' -d '{"run_id":"<run_id>","timeout_ms":30000,"include_result":true}'`
3. Optional coding-specialist routing (with fallback):
   - set `FRIDAY_CODER_ENABLED=1`, `FRIDAY_CODER_MODEL_NAME`, `FRIDAY_CODER_BASE_URL`
   - include `agent_profile:"coding"` or `use_coder_model:true` in chat/agent payload

## Interaction Policy Quick Check
1. Send `be brief` in a chat turn, then send a normal request.
2. Confirm `/api/chat` response `meta.interaction_mode` is `focused`.
3. Send `be human` and confirm `meta.interaction_mode` flips to `warm`.
4. Send `no banter` and confirm focused-style concise replies with no opener banter.

## Forcing CONFIRM_REQUIRED During Dev
First-pass sensitivity rules in FRIDAY heuristics mark candidates as confirm-required for:
- `kind` in `email | phone | address | ssn_like | medical`
- regex-detected email/phone values

Use a prompt with email/phone content, or stage a candidate directly in Muninn with `policy.requires_confirmation=true`.

## Operational Notes
- Browser must only call FRIDAY API; never call Muninn directly from frontend.
- `POST /api/memory/confirm` validates decision and `pending_ids` limits.
- `POST /api/memory/pending` resolves `entity_id` from request identity when omitted.
