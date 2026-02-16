#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${FRIDAY_BASE_URL:-http://127.0.0.1:${FRIDAY_API_PORT:-9001}}"
API_URL="${BASE_URL%/}/api"
DEVICE_ID="${FRIDAY_SMOKE_DEVICE_ID:-smoke-memory-device}"
MUNINN_BASE="${MUNINN_BASE_URL:-http://127.0.0.1:8000}"
FALLBACK_PORT="${FRIDAY_SMOKE_FALLBACK_PORT:-9011}"
SMOKE_DATA_DIR="${FRIDAY_SMOKE_DATA_DIR:-/tmp/friday_smoke_data}"

log() {
  printf '[smoke-memory] %s\n' "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3

log "Checking FRIDAY health at ${BASE_URL}/healthz"
curl -fsS "${BASE_URL}/healthz" >/dev/null

log "Sending chat turn through ${API_URL}/chat"
chat_response="$(curl -sS "${API_URL}/chat" \
  -H 'Content-Type: application/json' \
  -H "X-Friday-Device: ${DEVICE_ID}" \
  -d '{"prompt":"I prefer tea over coffee."}')"

python3 - "${chat_response}" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
text = str(data.get("text") or "")
if not text:
    raise SystemExit("chat response missing text")
memory = data.get("memory") if isinstance(data.get("memory"), dict) else {}
pending = memory.get("pending_ids") if isinstance(memory.get("pending_ids"), list) else []
print(f"chat_ok text_len={len(text)} pending_count={len(pending)}")
PY

log "Staging sensitive candidate directly in Muninn to attempt pending confirmation"
now_ts="$(python3 - <<'PY'
import time
print(time.time())
PY
)"
stage_payload="$(cat <<JSON
{"namespace":"friday","candidates":[{"kind":"preference","entity":{"id":"${DEVICE_ID}"},"payload":{"key":"account_password","value":"temporary-secret","tags":["preference"]},"confidence":0.96,"provenance":{"source_type":"user","source_id":"smoke_memory","note":"smoke","ts":${now_ts}}}],"ttl_seconds":86400}
JSON
)"
stage_response="$(curl -sS "${MUNINN_BASE%/}/v0/memory/stage_candidates" \
  -H 'Content-Type: application/json' \
  -d "${stage_payload}")"

pending_csv="$(python3 - "${stage_response}" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
pending = [str(item) for item in data.get("pending_ids", []) if str(item).strip()]
print(",".join(pending))
PY
)"

if [[ -n "${pending_csv}" ]]; then
  log "Confirming pending IDs through FRIDAY relay"
  confirm_payload="$(python3 - "${pending_csv}" <<'PY'
import json
import sys

pending = [p for p in sys.argv[1].split(",") if p]
print(json.dumps({"pending_ids": pending, "decision": "accept", "note": "smoke_accept_all"}))
PY
)"
  confirm_response="$(curl -sS "${API_URL}/memory/confirm" \
    -H 'Content-Type: application/json' \
    -H "X-Friday-Device: ${DEVICE_ID}" \
    -d "${confirm_payload}")"

  python3 - "${confirm_response}" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
memory = data.get("memory") if isinstance(data.get("memory"), dict) else {}
processed = int(memory.get("processed") or 0)
if processed < 1:
    raise SystemExit("memory confirm processed=0")
print(f"confirm_ok processed={processed}")
PY
else
  log "Muninn returned no pending IDs in this environment; validating confirm endpoint with synthetic ID"
  synthetic_response="$(curl -sS "${API_URL}/memory/confirm" \
    -H 'Content-Type: application/json' \
    -H "X-Friday-Device: ${DEVICE_ID}" \
    -d '{"pending_ids":["pending_synthetic"],"decision":"reject","note":"smoke_no_pending"}')"

  python3 - "${synthetic_response}" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
if not isinstance(data.get("memory"), dict):
    raise SystemExit("confirm endpoint missing memory payload")
print("confirm_route_ok synthetic")
PY
fi

log "Launching isolated backend with unreachable Muninn URL to verify graceful fallback"
fallback_log="$(mktemp)"
server_pid=""
cleanup() {
  if [[ -n "${server_pid}" ]]; then
    kill "${server_pid}" >/dev/null 2>&1 || true
    wait "${server_pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${fallback_log}"
}
trap cleanup EXIT

(
  cd "${ROOT_DIR}"
  FRIDAY_API_PORT="${FALLBACK_PORT}" \
  FRIDAY_LLM_ENABLED=0 \
  FRIDAY_MEMORY_PROVIDER=muninn \
  FRIDAY_DEBUG_MEMORY=0 \
  FRIDAY_DATA_DIR="${SMOKE_DATA_DIR}" \
  MUNINN_BASE_URL="http://127.0.0.1:65535" \
  python3 -m backend.main >"${fallback_log}" 2>&1
) &
server_pid="$!"

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${FALLBACK_PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
curl -fsS "http://127.0.0.1:${FALLBACK_PORT}/healthz" >/dev/null

fallback_chat="$(curl -sS "http://127.0.0.1:${FALLBACK_PORT}/api/chat" \
  -H 'Content-Type: application/json' \
  -H 'X-Friday-Device: smoke-fallback-device' \
  -d '{"prompt":"Fallback check"}')"

python3 - "${fallback_chat}" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
text = str(data.get("text") or "")
if not text:
    raise SystemExit("fallback chat missing text")
print("fallback_ok")
PY

kill "${server_pid}" >/dev/null 2>&1 || true
wait "${server_pid}" >/dev/null 2>&1 || true
server_pid=""
trap - EXIT
cleanup

log "All smoke checks passed"
