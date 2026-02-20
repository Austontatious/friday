#!/usr/bin/env bash
set -euo pipefail

APP_COMPOSE=${APP_COMPOSE:-docker-compose.app.yml}
BACKEND_PORT=${BACKEND_PORT:-9001}
MUNINN_PORT=${MUNINN_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-8080}

echo "==> Building and starting stack: $APP_COMPOSE"
env \
  FRIDAY_HOST_API_PORT="${BACKEND_PORT}" \
  FRIDAY_HOST_WEB_PORT="${FRONTEND_PORT}" \
  FRIDAY_HOST_MUNINN_PORT="${MUNINN_PORT}" \
  docker compose -f "$APP_COMPOSE" up -d --build

echo "==> Waiting for backend health..."
for i in {1..60}; do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/healthz" >/dev/null; then
    echo "backend healthy"
    break
  fi
  sleep 1
done

echo "==> Checking readiness..."
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/readyz" | sed -n '1,200p'

echo "==> Checking muninn..."
curl -fsS "http://127.0.0.1:${MUNINN_PORT}/health" | sed -n '1,200p'

echo "==> Checking frontend..."
curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null
echo "frontend OK"

echo "==> Checking frontend /api proxy..."
curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/healthz" | sed -n '1,200p'

echo "SMOKE PASS"
