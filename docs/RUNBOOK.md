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
