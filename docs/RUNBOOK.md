# FRIDAY Runbook

## Quick Start
- `cp .env.example .env`
- `docker compose up --build`
- Visit frontend + confirm `/healthz` and `/readyz`

## Modes
Text-only:
- disable all media services in `.env`
Text + Voice:
- enable STT + TTS, keep vision/gesture/avatar off
Full suite:
- enable everything + verify GPU availability

## Optional model services (profiles)
- Compose wiring lives in `docker-compose.models.yml` and is **opt-in** via profiles.
- Example (core + llm only):
  - `docker compose -f docker-compose.yaml -f docker-compose.models.yml --profile llm up -d`

## Health
- Backend: `/healthz` (basic) and `/readyz` (checks downstream deps)
- Each service must expose `/health`

## Common Failures
- Service enabled but unreachable → backend marks capability unavailable
- GPU out of memory → auto-disable high-cost features if configured
- Slow inference → job queue prevents request timeouts

## Logging
- Structured logs with request_id + user_id + job_id
- Keep logs volume reasonable; debug logs behind flag

## Debug APIs
- Memory debug endpoints are gated by `FRIDAY_DEBUG_APIS_ENABLED=1`
- Disable in production

## Eval Tripwire (pre-import baseline)
Run this before importing external references (e.g., Moltbot) to ensure the core loop hasn’t regressed:

```bash
FRIDAY_TOOLS_ENABLED=1 FRIDAY_TOOLS_REQUIRE_CONFIRM=1 FRIDAY_TRUST_MODE=strict FRIDAY_DEBUG_APIS_ENABLED=1 FRIDAY_MEMORY_FACTS_ENABLED=1 FRIDAY_MEMORY_SUMMARIES_ENABLED=1 FRIDAY_MEMORY_CONSOLIDATION_ENABLED=1 python3 tools/eval/smoke_eval.py && python3 tools/eval/regression_check.py --limit 5
```

## Muninn Memory Provider (Cutover)
- Select provider with `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none` (default `muninn`).
- Configure Muninn endpoint via `MUNINN_BASE_URL` and profile/namespace via `MUNINN_PROFILE`, `MUNINN_NAMESPACE`.
- Turn on `FRIDAY_DEBUG_MEMORY=1` to log injected `<SYSTEM_MEMORY>` snippets.
- Memory confirmation relay endpoints:
  - `POST /api/memory/confirm`
  - `POST /api/memory/pending`
- Run `bash scripts/smoke_memory.sh` for a quick end-to-end check.
