#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
PORT="${FRONTEND_E2E_PORT:-4173}"
API_PORT="${FRIDAY_API_PORT:-$(python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
)}"
SESSION_DIR="${FRIDAY_SKETCHMATH_SESSION_DIR:-$(mktemp -d /tmp/friday-sketchmath-e2e-sessions.XXXXXX)}"
BACKEND_LOG="${FRIDAY_SKETCHMATH_BACKEND_LOG:-/tmp/friday-sketchmath-e2e-backend.log}"
FRONTEND_LOG="${FRIDAY_SKETCHMATH_FRONTEND_LOG:-/tmp/friday-sketchmath-e2e-frontend.log}"

export FRIDAY_SKETCHMATH_ENABLED=1
export FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED=1
export REACT_APP_SKETCHMATH_ENABLED=1
export REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED=1
export FRIDAY_SKETCHMATH_SESSION_DIR="$SESSION_DIR"
export FRIDAY_API_PORT="$API_PORT"
export CI=true
export BROWSER=none

cleanup() {
  if [[ -n "${FRIDAY_BACKEND_PID:-}" ]] && kill -0 "$FRIDAY_BACKEND_PID" 2>/dev/null; then
    kill "$FRIDAY_BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd "$REPO_ROOT"
python3 -m backend.main >"$BACKEND_LOG" 2>&1 &
FRIDAY_BACKEND_PID=$!

cd "$ROOT_DIR"
PORT="$PORT" npm start >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

while true; do
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
    exit $?
  fi
  if ! kill -0 "$FRIDAY_BACKEND_PID" 2>/dev/null; then
    wait "$FRIDAY_BACKEND_PID"
    exit $?
  fi
  sleep 1
done
