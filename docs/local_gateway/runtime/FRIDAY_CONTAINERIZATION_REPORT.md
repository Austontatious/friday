# Friday Containerization Report

Date: 2026-06-12
Host: `unix-X10SLH-N6-ST031`
Branch: `phase0-stabilize`
Commit: `deee4dd`

## Scope

Move the validated Friday runtime from a host-run backend process into the containerized Friday stack while preserving:

- direct Friday chat
- coder routing
- Althing bridge fallback behavior
- local gateway ownership of model serving

## Starting State

- Host-run Friday backend was still bound to `127.0.0.1:9001`
- Compose Friday backend was present but published on `19001 -> 9001`
- Local gateway was healthy on `127.0.0.1:8130`
- Gateway aliases were healthy:
  - `friday` -> `127.0.0.1:8174/v1`
  - `friday-coder` -> `127.0.0.1:8176/v1`
- Backend container had `extra_hosts: host.docker.internal:host-gateway`
- Backend container env was stale for containerized Althing access:
  - `FRIDAY_ALTHING_BASE_URL=http://localhost:8010`
  - `FRIDAY_CODER_BASE_URL=http://host.docker.internal:8008`

## Findings

- The backend container can reach the host gateway through `host.docker.internal`.
- The backend container can reach the Althing router via the in-network `althing_router:8000` alias.
- The main containerization blocker was configuration, not Docker networking:
  - Althing base URL needed to target the router container, not localhost.
  - Backend runtime env needed to use the host gateway for the local model bridge.

## Fixes Applied

1. `docker-compose.app.yml`
   - Set backend container defaults for:
     - `LLM_BASE_URL=http://host.docker.internal:8130/v1`
     - `FRIDAY_MODEL_NAME=friday`
     - `FRIDAY_CODER_BASE_URL=http://host.docker.internal:8130/v1`
     - `FRIDAY_CODER_MODEL_NAME=friday-coder`
     - `FRIDAY_ALTHING_BASE_URL=http://althing_router:8000`
     - `FRIDAY_ALTHING_MODEL_HINT=auto_no_reason`

2. `scripts/friday_up.sh`
   - Writes container-safe runtime env values into `.env.runtime`
   - Records the Althing router origin as `http://althing_router:8000`

## Verification Targets

Pending after stack restart:

- backend container owns host port `9001`
- `docker exec <backend>` can reach:
  - `http://host.docker.internal:8130/health`
  - `http://host.docker.internal:8130/v1/models`
  - `http://althing_router:8000/chat/completions`
- `GET /healthz` and `GET /readyz` on `127.0.0.1:9001`
- `POST /api/chat`
- `POST /api/chat` with `use_coder_model=true`
- `POST /api/althing/chat`

## Current Status

In progress. The deployment config is now container-oriented; the next step is restart and live smoke validation with the container owning `9001`.

## Milestone 1.1 - Capture State (June 12, 2026)

- **Commit**: `deee4dd` (Make Althing bridge degrade to direct Friday runtime)
- **Container status**:
  - `friday-friday-backend-1` is running (healthy) and bound to host port `9001`.
  - `friday-friday-frontend-1` is running and bound to host port `18080`.
- **Host Listening Ports**:
  - `8130` (local_llm_gateway)
  - `8174` (llama-server - primary)
  - `8176` (llama-server - coder)
  - `9001` (friday-backend container binding)
  - `18080` (friday-frontend container binding)
  - `18000` (friday-muninn container binding)
- **Container health check results (Initial)**:
  - `healthz`: `{"ok":true}`
  - `readyz`: `{"ok":false}`. The `llm` and `coder` services report unhealthy/unreachable because the host firewall drops docker-bridge traffic to the host gateway at port `8130`.
