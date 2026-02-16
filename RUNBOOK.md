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
export MUNINN_BASE_URL=http://127.0.0.1:8000
export MUNINN_NAMESPACE=friday
export MUNINN_PROFILE=friday
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

## Smoke Script
```bash
bash scripts/smoke_memory.sh
```
