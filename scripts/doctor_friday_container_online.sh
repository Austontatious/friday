#!/usr/bin/env bash
set -euo pipefail

BACKEND_CONTAINER="${BACKEND_CONTAINER:-friday-friday-backend-1}"
BACKEND_BASE="${BACKEND_BASE:-http://127.0.0.1:9001}"
FRONTEND_BASE="${FRONTEND_BASE:-http://127.0.0.1:18080}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

post_json() {
  local url="$1"
  local body="$2"
  curl -sS --max-time 120 "$url" \
    -H 'Content-Type: application/json' \
    -d "$body"
}

require_cmd curl
require_cmd jq
require_cmd docker

docker inspect "$BACKEND_CONTAINER" >/dev/null 2>&1 || fail "backend container not found: $BACKEND_CONTAINER"
pass "backend container exists: $BACKEND_CONTAINER"

# Validate model identities over the same network path used by Friday. A reachable
# host port serving a different model is unhealthy.
docker exec -i "$BACKEND_CONTAINER" python3 - <<'PY' || fail "backend model identity check failed"
import json
import os
import urllib.request

checks = [
    ("LLM_BASE_URL", "FRIDAY_MODEL_NAME"),
    ("FRIDAY_CODER_BASE_URL", "FRIDAY_CODER_MODEL_NAME"),
]
for base_key, model_key in checks:
    base = os.environ.get(base_key, "").rstrip("/")
    expected = os.environ.get(model_key, "").strip()
    if not base or not expected:
        raise SystemExit(f"missing {base_key} or {model_key}")
    url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)
    observed = {str(item.get("id", "")) for item in payload.get("data", []) if isinstance(item, dict)}
    if expected not in observed:
        raise SystemExit(f"{base_key} expected {expected!r}, observed {sorted(observed)!r}")
    print(f"{base_key}: expected model {expected!r} is reachable")
PY
pass "backend model identities"

# Check backend health/readiness
curl -sS --max-time 10 "$BACKEND_BASE/healthz" | jq -e '.ok == true' >/dev/null || fail "backend healthz unhealthy"
pass "backend healthz"

curl -sS --max-time 10 "$BACKEND_BASE/readyz" | jq -e '.ok == true' >/dev/null || fail "backend readyz unhealthy"
pass "backend readyz"

# Direct chat smoke
DIRECT="$(post_json "$BACKEND_BASE/api/chat" '{"message":"Doctor direct smoke. Reply exactly: doctor-direct-ok"}')"
echo "$DIRECT" | jq . >/dev/null || fail "direct chat did not return valid JSON"
echo "$DIRECT" | grep -qi "doctor-direct-ok" || fail "direct chat response did not contain expected marker"
pass "direct chat"

# Coder route smoke
CODER="$(post_json "$BACKEND_BASE/api/chat" '{"message":"Doctor coder smoke. Reply exactly: doctor-coder-ok","use_coder_model":true}')"
echo "$CODER" | jq . >/dev/null || fail "coder chat did not return valid JSON"
echo "$CODER" | grep -qi "doctor-coder-ok" || fail "coder chat response did not contain expected marker"
pass "coder route"

if curl -sS -I --max-time 10 "$FRONTEND_BASE" >/dev/null 2>&1; then
  pass "frontend reachable"
else
  echo "WARN: frontend not reachable at $FRONTEND_BASE"
fi

echo "Friday container runtime doctor: PASS"
