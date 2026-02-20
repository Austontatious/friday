# RUNBOOK

## Muninn + FRIDAY Memory Provider Quickstart

1. Start Muninn:
```bash
curl -sS http://127.0.0.1:8000/health
```
Expected: `{"ok": true}`.

2. Configure FRIDAY (example):
```bash
export FRIDAY_MEMORY_PROVIDER=muninn
export FRIDAY_MEMORY_FALLBACK_PROVIDER=legacy
export FRIDAY_MODEL_NAME=Lexi
export LLM_BASE_URL=http://127.0.0.1:8008
export FRIDAY_INTERACTION_DEFAULT_MODE=neutral
export FRIDAY_INTERACTION_ONE_SCREEN_CHARS=900
export FRIDAY_INTERACTION_PLAYFUL_ENABLED=0
export MUNINN_BASE_URL=http://127.0.0.1:8000
export MUNINN_NAMESPACE=friday
export MUNINN_PROFILE=friday
export MUNINN_CONNECT_TIMEOUT_SECONDS=2
export MUNINN_READ_TIMEOUT_SECONDS=5
export MUNINN_HTTP_OVERALL_TIMEOUT_SECONDS=7
export FRIDAY_DEBUG_MEMORY=1
export FRIDAY_DATA_DIR=/tmp/friday_data
```

3. Start FRIDAY backend:
```bash
python -m backend.main
```

4. Verify memory injection path:
```bash
curl -sS http://127.0.0.1:9001/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Friday-Device: runbook-device' \
  -d '{"prompt":"I prefer tea."}'
```
Check backend logs for injected `<SYSTEM_MEMORY>` when `FRIDAY_DEBUG_MEMORY=1`.
Response should include `memory.provider`.

5. Verify confirmation relay:
```bash
curl -sS http://127.0.0.1:9001/api/memory/confirm \
  -H 'Content-Type: application/json' \
  -H 'X-Friday-Device: runbook-device' \
  -d '{"pending_ids":["pending_test_id"],"decision":"reject"}'
```

6. Verify graceful fallback when Muninn is unreachable:
```bash
FRIDAY_MEMORY_PROVIDER=muninn MUNINN_BASE_URL=http://127.0.0.1:65535 python -m backend.main
```
Send `/api/chat`; FRIDAY should still reply while logging fallback warning.

## Agentic Run API

Submit:
```bash
curl -sS http://127.0.0.1:9001/api/agent \
  -H 'Content-Type: application/json' \
  -H 'X-Friday-Device: runbook-device' \
  -d '{"prompt":"Plan this migration in steps","idempotency_key":"runbook-agent-1"}'
```

Wait:
```bash
curl -sS http://127.0.0.1:9001/api/agent/wait \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"<run_id_from_submit>","timeout_ms":30000,"include_result":true}'
```

## Interaction Policy Check
1. Send `be brief` in a first turn.
2. Send a follow-up task turn.
3. Verify `/api/chat` response metadata includes `interaction_mode: focused`.

## Smoke Script
```bash
bash scripts/smoke_memory.sh
```
