#!/usr/bin/env bash
set -euo pipefail

PUBLIC_BASE="${PUBLIC_BASE:-https://friday.austontatious.dev}"

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

echo "Checking Friday Public Deployment at: $PUBLIC_BASE"

# Check root page
curl -sS -I --max-time 20 "$PUBLIC_BASE" >/dev/null || fail "Public root URL not reachable"
pass "public root reachable"

# Check direct chat route
DIRECT="$(post_json "$PUBLIC_BASE/api/chat" '{"message":"Public direct smoke. Reply exactly: public-friday-ok"}')"
echo "$DIRECT" | jq . >/dev/null || fail "public direct chat did not return valid JSON"
echo "$DIRECT" | grep -qi "public-friday-ok" || fail "public direct chat response did not contain expected marker"
pass "public direct chat"

echo "Friday public deployment doctor: PASS"
