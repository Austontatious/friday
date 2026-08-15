#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

APP_COMPOSE=${APP_COMPOSE:-docker-compose.app.yml}
MODELS_COMPOSE=${MODELS_COMPOSE:-docker-compose.models.yml}

# Preferences / defaults
HOST_MUNINN_URL_DEFAULT=${HOST_MUNINN_URL_DEFAULT:-http://127.0.0.1:8000}
HOST_GATEWAY_URL_DEFAULT=${HOST_GATEWAY_URL_DEFAULT:-http://127.0.0.1:8130}
HOST_LLM_URL_DEFAULT=${HOST_LLM_URL_DEFAULT:-http://127.0.0.1:8104}
HOST_CODER_URL_DEFAULT=${HOST_CODER_URL_DEFAULT:-http://127.0.0.1:8105}
COMPOSE_GATEWAY_URL=${COMPOSE_GATEWAY_URL:-http://host.docker.internal:8130/v1}
COMPOSE_MUNINN_URL=${COMPOSE_MUNINN_URL:-http://muninn:8000}
COMPOSE_LLM_URL=${COMPOSE_LLM_URL:-http://llm:8000}
COMPOSE_CODER_URL=${COMPOSE_CODER_URL:-http://friday-coder:8010}
DOCKER_HOST_ALIAS=${DOCKER_HOST_ALIAS:-host.docker.internal}

AUTO_START_MODELS=${AUTO_START_MODELS:-1}
AUTO_START_MUNINN=${AUTO_START_MUNINN:-1}
CODER_ENABLED="${FRIDAY_CODER_ENABLED:-}"
LLM_ENABLED="${FRIDAY_LLM_ENABLED:-}"
LLM_MODEL_NAME="${FRIDAY_MODEL_NAME:-exec}"
FRIDAY_CODER_MODEL_NAME="${FRIDAY_CODER_MODEL_NAME:-coder}"

probe_json() {
  local url="$1"
  curl -fsS --max-time 1 "$url" >/dev/null 2>&1
}

probe_llm_models() {
  local base="$1"
  local expected="${2:-}"
  local out
  local models_url="${base%/}"
  if [[ "$models_url" == */v1 ]]; then
    models_url="${models_url}/models"
  else
    models_url="${models_url}/v1/models"
  fi
  out="$(curl -fsS --max-time 1 "$models_url" 2>/dev/null || true)"
  if [[ -z "$out" ]]; then
    return 1
  fi
  if ! echo "$out" | grep -q '"data"'; then
    return 1
  fi
  if [[ -n "$expected" ]]; then
    echo "$out" | grep -q "\"id\"[[:space:]]*:[[:space:]]*\"${expected}\""
  fi
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" | awk 'NR>1 {found=1} END {exit(found?0:1)}'
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -nP >/dev/null 2>&1
  else
    nc -z 127.0.0.1 "${port}" >/dev/null 2>&1
  fi
}

choose_host_port() {
  local default_port="$1"
  local fallback_port="$2"
  local env_var_name="$3"
  local env_value="${!env_var_name-}"

  if [[ -n "${env_value}" ]]; then
    echo "${env_value}"
    return
  fi

  if port_in_use "${default_port}"; then
    echo "${fallback_port}"
  else
    echo "${default_port}"
  fi
}

to_container_url() {
  local url="$1"
  echo "$url" | sed -E "s#://(127\\.0\\.0\\.1|localhost)([:/])#://${DOCKER_HOST_ALIAS}\\2#"
}

choose_muninn_host_port() {
  if [[ "${MUNINN_BASE_URL}" == "${COMPOSE_MUNINN_URL}" ]]; then
    choose_host_port "8000" "18000" "FRIDAY_HOST_MUNINN_PORT"
  else
    # Avoid host-port collision when using external Muninn.
    echo "18000"
  fi
}

echo "==> FRIDAY autodiscovery"

MUNINN_BASE_URL=""
if probe_json "${HOST_MUNINN_URL_DEFAULT}/health"; then
  MUNINN_BASE_URL="$(to_container_url "${HOST_MUNINN_URL_DEFAULT}")"
  echo "Muninn: using host at ${MUNINN_BASE_URL}"
else
  if [[ "${AUTO_START_MUNINN}" == "1" ]]; then
    echo "Muninn: host not reachable; will use compose service (${COMPOSE_MUNINN_URL})"
    MUNINN_BASE_URL="${COMPOSE_MUNINN_URL}"
  else
    echo "Muninn: host not reachable and AUTO_START_MUNINN=0; leaving unset"
  fi
fi

LLM_BASE_URL="${LLM_BASE_URL:-}"
if probe_llm_models "${HOST_GATEWAY_URL_DEFAULT}" "friday" && probe_llm_models "${HOST_GATEWAY_URL_DEFAULT}" "friday-coder"; then
  LLM_BASE_URL="$(to_container_url "${HOST_GATEWAY_URL_DEFAULT}")"
  LLM_MODEL_NAME="friday"
  LLM_ENABLED="1"
  CODER_BASE_URL="$(to_container_url "${HOST_GATEWAY_URL_DEFAULT}")"
  CODER_ENABLED="1"
  FRIDAY_CODER_MODEL_NAME="friday-coder"
  echo "LLM: using host local gateway at ${LLM_BASE_URL}"
elif [[ -n "${LLM_BASE_URL:-}" ]]; then
  if ! probe_llm_models "${LLM_BASE_URL}" "${LLM_MODEL_NAME}"; then
    echo "LLM: manual endpoint does not serve expected model '${LLM_MODEL_NAME}': ${LLM_BASE_URL}" >&2
    exit 1
  fi
  LLM_BASE_URL="$(to_container_url "${LLM_BASE_URL}")"
  LLM_ENABLED="1"
  echo "LLM: verified manual endpoint at ${LLM_BASE_URL}"
else
  EXPECTED_LLM_MODEL="${LLM_MODEL_NAME}"
  if probe_llm_models "${HOST_LLM_URL_DEFAULT}" "${EXPECTED_LLM_MODEL}"; then
    LLM_BASE_URL="$(to_container_url "${HOST_LLM_URL_DEFAULT}")"
    LLM_ENABLED="1"
    echo "LLM: using identity-verified host endpoint at ${LLM_BASE_URL}"
  else
    if [[ "${AUTO_START_MODELS}" == "1" ]]; then
      echo "LLM: host not reachable; will use compose gateway service (${COMPOSE_GATEWAY_URL})"
      LLM_BASE_URL="${COMPOSE_GATEWAY_URL}"
      LLM_ENABLED="1"
    else
      echo "LLM: host not reachable and AUTO_START_MODELS=0; leaving unset"
    fi
  fi
fi

CODER_BASE_URL="${CODER_BASE_URL:-}"
if [[ -z "${CODER_BASE_URL}" && ( -z "${CODER_ENABLED}" || "${CODER_ENABLED}" == "1" ) ]]; then
  EXPECTED_CODER_MODEL="${FRIDAY_CODER_MODEL_NAME}"
  if probe_llm_models "${HOST_CODER_URL_DEFAULT}" "${EXPECTED_CODER_MODEL}"; then
    CODER_BASE_URL="$(to_container_url "${HOST_CODER_URL_DEFAULT}")"
    CODER_ENABLED="1"
    echo "Coder LLM: using identity-verified host endpoint at ${CODER_BASE_URL}"
  else
    if [[ "${AUTO_START_MODELS}" == "1" ]]; then
      echo "Coder LLM: host not reachable; will use compose model service (${COMPOSE_CODER_URL})"
      CODER_BASE_URL="${COMPOSE_CODER_URL}"
      CODER_ENABLED="1"
    else
      echo "Coder LLM: host not reachable and AUTO_START_MODELS=0; leaving unset"
    fi
  fi
else
  if [[ -n "${CODER_BASE_URL}" ]] && [[ "${CODER_ENABLED:-1}" == "1" ]]; then
    if ! probe_llm_models "${CODER_BASE_URL}" "${FRIDAY_CODER_MODEL_NAME}"; then
      echo "Coder LLM: manual endpoint does not serve expected model '${FRIDAY_CODER_MODEL_NAME}': ${CODER_BASE_URL}" >&2
      exit 1
    fi
    CODER_BASE_URL="$(to_container_url "${CODER_BASE_URL}")"
    CODER_ENABLED="1"
    echo "Coder LLM: verified manual endpoint at ${CODER_BASE_URL}"
  else
    echo "Coder LLM disabled by FRIDAY_CODER_ENABLED=${CODER_ENABLED}; skipping coder discovery"
  fi
fi

# Ensure LLM_BASE_URL and CODER_BASE_URL end in /v1 if they target the gateway
if [[ "${LLM_BASE_URL}" == *":8130" || "${LLM_BASE_URL}" == *":8130/" ]]; then
  LLM_BASE_URL="${LLM_BASE_URL%/}/v1"
fi
if [[ "${CODER_BASE_URL}" == *":8130" || "${CODER_BASE_URL}" == *":8130/" ]]; then
  CODER_BASE_URL="${CODER_BASE_URL%/}/v1"
fi

cat > .env.runtime <<EOF
# Auto-generated by scripts/friday_up.sh
MUNINN_BASE_URL=${MUNINN_BASE_URL}
LLM_BASE_URL=${LLM_BASE_URL}
FRIDAY_LLM_ENABLED=${LLM_ENABLED:-0}
FRIDAY_MODEL_NAME=${LLM_MODEL_NAME}
FRIDAY_CODER_ENABLED=${CODER_ENABLED:-0}
FRIDAY_CODER_BASE_URL=${CODER_BASE_URL}
FRIDAY_CODER_MODEL_NAME=${FRIDAY_CODER_MODEL_NAME}
EOF

echo "==> Wrote .env.runtime"
sed -n '1,120p' .env.runtime

export MUNINN_BASE_URL
export LLM_BASE_URL
export FRIDAY_LLM_ENABLED
export FRIDAY_MODEL_NAME
export FRIDAY_CODER_ENABLED
export FRIDAY_CODER_BASE_URL
export FRIDAY_CODER_MODEL_NAME

RESOLVED_MUNINN_HOST_PORT="$(choose_muninn_host_port)"
RESOLVED_API_HOST_PORT="$(choose_host_port "9001" "19001" "FRIDAY_HOST_API_PORT")"
RESOLVED_WEB_HOST_PORT="$(choose_host_port "8080" "18080" "FRIDAY_HOST_WEB_PORT")"
USE_COMPOSE_MUNINN=0
if [[ "${MUNINN_BASE_URL}" == "${COMPOSE_MUNINN_URL}" ]]; then
  USE_COMPOSE_MUNINN=1
fi

if [[ -z "${FRIDAY_HOST_API_PORT:-}" ]] && [[ "${RESOLVED_API_HOST_PORT}" != "9001" ]]; then
  echo "Backend port 9001 busy; using ${RESOLVED_API_HOST_PORT}"
fi
if [[ -z "${FRIDAY_HOST_WEB_PORT:-}" ]] && [[ "${RESOLVED_WEB_HOST_PORT}" != "8080" ]]; then
  echo "Frontend port 8080 busy; using ${RESOLVED_WEB_HOST_PORT}"
fi

echo "==> Starting app stack: ${APP_COMPOSE}"
if [[ "${USE_COMPOSE_MUNINN}" == "1" ]]; then
  FRIDAY_HOST_API_PORT="${RESOLVED_API_HOST_PORT}" \
  FRIDAY_HOST_WEB_PORT="${RESOLVED_WEB_HOST_PORT}" \
  FRIDAY_HOST_MUNINN_PORT="${RESOLVED_MUNINN_HOST_PORT}" \
    docker compose -f "${APP_COMPOSE}" up -d --build
else
  echo "==> Starting backend/frontend only (external Muninn or disabled Muninn)"
  echo "==> Ensuring writable backend volumes (/data, /logs)"
  docker compose -f "${APP_COMPOSE}" up -d friday-volume-init
  FRIDAY_HOST_API_PORT="${RESOLVED_API_HOST_PORT}" \
  FRIDAY_HOST_WEB_PORT="${RESOLVED_WEB_HOST_PORT}" \
  FRIDAY_HOST_MUNINN_PORT="${RESOLVED_MUNINN_HOST_PORT}" \
    docker compose -f "${APP_COMPOSE}" up -d --build --no-deps friday-gateway-firewall friday-backend friday-frontend
fi

if [[ "${AUTO_START_MODELS}" == "1" ]] && [[ "${LLM_BASE_URL}" == "${COMPOSE_GATEWAY_URL}" || "${CODER_BASE_URL}" == "${COMPOSE_CODER_URL}" ]]; then
  echo "==> Starting models stack: ${MODELS_COMPOSE}"
  docker compose -f "${MODELS_COMPOSE}" --profile models up -d || true
fi

echo "==> Done. Frontend: http://127.0.0.1:${RESOLVED_WEB_HOST_PORT}  Backend: http://127.0.0.1:${RESOLVED_API_HOST_PORT}  Muninn: ${MUNINN_BASE_URL}  LLM: ${LLM_BASE_URL}  Coder LLM: ${CODER_BASE_URL}"
