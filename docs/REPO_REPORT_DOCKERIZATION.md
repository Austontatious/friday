# FRIDAY Repo Report for Dockerization and Production Hardening

Date: 2026-02-20  
Repo: `/mnt/data/friday`  
Commit inspected: `7853b12` (`baseline: agentic spine + UX policy kernel + Muninn reliability`)

## Repo Snapshot

### Identity and status

```bash
$ cd /mnt/data/friday
$ pwd
/mnt/data/friday

$ git rev-parse --is-inside-work-tree
true

$ git status --short
# (clean)

$ git log -1 --oneline
7853b12 baseline: agentic spine + UX policy kernel + Muninn reliability
```

### Top-level layout (`ls -la` highlights)

Key top-level paths:
- `backend/` (FastAPI backend, memory/tool/agentic core)
- `frontend/` (React UI; CRA scripts present, Vite config also present)
- `docs/` (architecture/runbook/decisions)
- `scripts/` (smoke checks and utility scripts)
- `tests/` (pytest suite)
- `docker-compose.yaml` and `docker-compose.models.yml`
- `Dockerfile` (backend image)

## Directory Structure

## Depth-limited map (`tree -L 4` with excludes)

```text
.
├── backend
│   ├── agentic
│   ├── api
│   ├── core
│   ├── identity
│   ├── jobs
│   ├── memory
│   ├── middleware
│   ├── security
│   ├── tools
│   └── workspaces
├── frontend
│   ├── public
│   ├── src
│   │   ├── components
│   │   ├── services
│   │   └── types
│   └── vite.config.ts
├── docs
├── scripts
├── services
│   ├── models
│   │   ├── code
│   │   ├── llm
│   │   ├── omni
│   │   ├── stt
│   │   └── vlm
│   └── repos
├── tests
└── Dockerfile / docker-compose*.yml / requirements.txt
```

## Backend Summary

### Framework and entrypoints

- Framework: FastAPI + Starlette middleware
- Primary app module: `backend/main.py`
  - `create_app()` builds FastAPI app and mounts routers
  - `run()` executes `uvicorn.run("backend.main:app", host="0.0.0.0", port=FRIDAY_API_PORT)`
- Direct run path:
  - `python -m backend.main` (used by `start.sh` and `Dockerfile CMD`)

### Router map and API route overview

Mounted in `backend/main.py` with `/api` prefix (except health and root):

| Method | Route | Source file | Purpose |
|---|---|---|---|
| GET | `/` | `backend/main.py` | root status |
| GET | `/healthz` | `backend/api/health.py` | liveness |
| GET | `/readyz` | `backend/api/health.py` | readiness with dependency checks |
| POST | `/api/chat` | `backend/api/chat.py` | synchronous chat |
| GET | `/api/capabilities` | `backend/api/capabilities.py` | enabled/available matrix |
| POST | `/api/agent` | `backend/api/agent.py` | submit async agent run |
| POST | `/api/agent/wait` | `backend/api/agent.py` | wait for run completion |
| GET | `/api/agent/{run_id}` | `backend/api/agent.py` | poll run status |
| POST | `/api/memory/confirm` | `backend/api/memory_provider.py` | confirm pending memory items |
| POST | `/api/memory/pending` | `backend/api/memory_provider.py` | list pending items |
| POST | `/api/jobs` | `backend/api/jobs.py` | create async job (memory backend now) |
| GET | `/api/jobs/{job_id}` | `backend/api/jobs.py` | job status |
| GET | `/api/jobs/{job_id}/result` | `backend/api/jobs.py` | job result |
| POST | `/api/stt` | `backend/api/stubs.py` | STT stub gated by flag |
| POST | `/api/tts` | `backend/api/stubs.py` | TTS stub gated by flag |
| POST | `/api/vision` | `backend/api/stubs.py` | vision stub gated by flag |
| POST | `/api/avatar` | `backend/api/stubs.py` | avatar stub gated by flag |

Debug routes (off by default via `FRIDAY_DEBUG_APIS_ENABLED`):  
`/api/memory/facts`, `/api/memory/summaries`, `/api/memory/consolidate`.

### Core backend architecture

- Chat orchestrator: `backend/core/chat_engine.py`
  - Builds interaction policy (`focused|neutral|warm`, playful gated)
  - Rehydrates memory from provider, injects `<SYSTEM_MEMORY>`
  - LLM call path with coder-route optional fallback to primary route
  - Tool-call parse/execute path with trust/confirmation gates
  - Deterministic response shaping (`backend/core/response_shaper.py`)
  - Candidate memory extraction and staging after reply
- LLM abstraction: `backend/core/llm.py`
  - OpenAI-compatible remote endpoint via `LLM_BASE_URL`
  - Default model name: `FRIDAY_MODEL_NAME=Lexi`
  - Optional local `llama-cpp` model path mode
- Prompt builder: `backend/core/prompt_builder.py`
  - Prompt profile templating
  - Capability and memory-context insertion
  - Interaction policy block injection (advisory for model behavior)
- Agentic spine: `backend/agentic/*`
  - Submit/wait/status APIs
  - Queue lane controls (`main`, `subagent`) with per-session serialization
  - Runtime event stream dispatch (`lifecycle`, `tool`, `assistant`, `runtime`)
- Identity middleware:
  - Resolves user identity from account/session/device headers/cookies
  - Writes `X-Friday-User` and identity-source header

### Model and memory integrations

- Primary model route:
  - `FRIDAY_MODEL_NAME` defaults to `Lexi`
  - `LLM_BASE_URL` controls upstream OpenAI-compatible endpoint (e.g., vLLM)
- Optional coding specialist route:
  - `FRIDAY_CODER_ENABLED`, `FRIDAY_CODER_BASE_URL`, `FRIDAY_CODER_MODEL_NAME`
  - Falls back to primary model on route failure
- Memory provider:
  - `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none`
  - Muninn provider uses HTTP client with connect/read/overall timeout + retry
  - Fallback provider wrapper protects chat continuity on memory errors

### Backend runtime ports and URLs

- Backend bind: `0.0.0.0:${FRIDAY_API_PORT:-9001}`
- Compose backend published port: `${FRIDAY_API_PORT:-9001}:9001`
- Muninn default in compose: `http://muninn:8000`
- Muninn local-host fallback defaults in code: `http://127.0.0.1:8000`

### Backend env vars (major contract set)

| Env var | Where used | Purpose | Default |
|---|---|---|---|
| `FRIDAY_API_PORT` | `backend/main.py`, compose | API bind/publish port | `9001` |
| `FRIDAY_LLM_ENABLED` | `backend/core/llm.py`, capabilities | Toggle LLM capability | `0` in `.env.example` |
| `FRIDAY_MODEL_NAME` | `backend/core/llm.py`, compose | Model id for OpenAI-compatible call | `Lexi` |
| `LLM_BASE_URL` | `backend/core/llm.py` | Primary remote LLM endpoint | `http://llm:8000` in `.env.example` |
| `FRIDAY_CODER_ENABLED` | `backend/core/chat_engine.py` | Enable specialist coder route | `0` |
| `FRIDAY_CODER_BASE_URL` | `backend/core/chat_engine.py` | Specialist endpoint | empty |
| `FRIDAY_CODER_MODEL_NAME` | `backend/core/chat_engine.py` | Specialist model name | empty |
| `FRIDAY_TOOLS_ENABLED` | `backend/tools/engine.py` | Tool execution gating | `0` |
| `FRIDAY_TOOLS_REQUIRE_CONFIRM` | `backend/tools/engine.py` | Default confirm requirement | `1` |
| `FRIDAY_TRUST_MODE` | `backend/security/trust.py` | strict/dev trust handling | `strict` |
| `FRIDAY_TRUST_SAFE_TOOLS` | `backend/security/trust.py` | allowlist for untrusted contexts | `list_facts,search_local_logs` |
| `FRIDAY_MEMORY_PROVIDER` | `backend/memory/factory.py` | Memory backend select | `muninn` |
| `FRIDAY_MEMORY_FALLBACK_PROVIDER` | `backend/memory/factory.py` | Fallback provider | `legacy` |
| `MUNINN_BASE_URL` | `backend/memory/factory.py`, provider | Muninn endpoint | `http://muninn:8000` in compose |
| `MUNINN_NAMESPACE` | `backend/memory/factory.py` | Memory namespace | `friday` |
| `MUNINN_PROFILE` | `backend/memory/factory.py` | Memory profile | `friday` |
| `MUNINN_REQUIRE_API_KEY` | `backend/memory/muninn_client.py` | Enforce API key usage | `0` |
| `MUNINN_API_KEY` | `backend/memory/muninn_client.py` | Muninn API key | empty |
| `MUNINN_CONNECT_TIMEOUT_SECONDS` | `backend/memory/muninn_client.py` | HTTP connect timeout | `2` |
| `MUNINN_READ_TIMEOUT_SECONDS` | `backend/memory/muninn_client.py` | HTTP read timeout | `5` |
| `MUNINN_HTTP_OVERALL_TIMEOUT_SECONDS` | `backend/memory/muninn_client.py` | overall request timeout | `7` |
| `MUNINN_HTTP_RETRIES` | `backend/memory/muninn_client.py` | retry count (extra attempts) | `1` |
| `MUNINN_HTTP_RETRY_BACKOFF_SECONDS` | `backend/memory/muninn_client.py` | retry backoff | `0.2` |
| `FRIDAY_INTERACTION_DEFAULT_MODE` | `backend/core/interaction_policy.py` | policy default mode | `neutral` |
| `FRIDAY_INTERACTION_ONE_SCREEN_CHARS` | `backend/core/interaction_policy.py` | deterministic output cap | `900` |
| `FRIDAY_INTERACTION_PLAYFUL_ENABLED` | `backend/core/interaction_policy.py` | playful hard gate | `0` |
| `FRIDAY_DATA_DIR` | memory/audit modules | persistent data path | `/data` |
| `FRIDAY_LOG_DIR` | runtime scripts/env | log path | `/logs` |
| `FRIDAY_QUEUE_BACKEND` | `backend/jobs/store.py` | job backend (`memory|redis`) | `memory` |
| `REDIS_URL` | health checks | redis probe target (if queue backend redis) | `redis://redis:6379/0` |

## Frontend Summary

### Toolchain and entrypoints

- `frontend/package.json` scripts are Create React App (`react-scripts`)
  - `start`, `dev`, `build`, `test`, `eject`
- Entrypoint: `frontend/src/index.tsx` -> renders `App` inside `ChakraProvider`
- Main app component: `frontend/src/App.tsx`
- API client: `frontend/src/services/api.ts`

### API base URL behavior

- `frontend/src/services/api.ts` uses:
  - `const API_URL = process.env.REACT_APP_API_URL || "/api"`
- `frontend/package.json` has CRA proxy:
  - `"proxy": "http://localhost:9001"`
- `frontend/vite.config.ts` exists and proxies `/api` and `/ws` to localhost backend, but package scripts currently do not invoke Vite.
- `frontend/.env` contains `VITE_*` values, which are not consumed by CRA runtime path.

### Frontend scripts and dependencies

`frontend/package.json` scripts:
- `start`: `react-scripts start`
- `dev`: `react-scripts start`
- `build`: `react-scripts build`
- `test`: `react-scripts test`
- `eject`: `react-scripts eject`

Key frontend dependencies:
- `react`, `react-dom`, `react-router-dom`
- `@chakra-ui/react`, `@emotion/*`, `framer-motion`
- `axios`, TypeScript toolchain

Frontend lockfile present:
- `frontend/package-lock.json`

### Frontend env vars table

| Env var | Where used | Purpose | Notes |
|---|---|---|---|
| `REACT_APP_API_URL` | `frontend/src/services/api.ts` | API base URL override | default falls back to `/api` |
| `FRIDAY_API_PORT` | `frontend/vite.config.ts` | backend proxy target port | only used if running via Vite |
| `PORT` | `frontend/vite.config.ts` | Vite dev server port | only used if running via Vite |
| `VITE_BACKEND_URL` | `frontend/src/vite-env.d.ts` typing | type declaration only | not used in current CRA scripts |
| `VITE_*` in `frontend/.env` | local env file | intended for Vite | currently mismatched with CRA runtime path |

## Compose and Runtime

### `docker-compose.yaml` (primary runtime)

Services:
- `friday-backend`
  - Build context: repo root
  - Exposes port `9001`
  - Mounts entire repo `.:/app`
  - Depends on `muninn` (condition: service_started)
  - Healthcheck: `GET /healthz`
- `muninn`
  - Image `ghcr.io/austontatious/muninn:latest` (default)
  - Exposes port `8000`
  - Healthcheck: `GET /health`

Network:
- `friday_net` bridge defined in file

### `docker-compose.models.yml` (model profile services)

Services:
- `llm` (vLLM OpenAI-compatible, served model defaults to `Lexi`)
- `vision` (vLLM-based)
- `stt`, `tts`, `avatar` (scaffolds/sleep)

Observation:
- Services reference network `friday_net`, but this file has no `networks:` definition block. It assumes composition with a file that defines `friday_net`.

### Current runtime assumptions and contracts

- Backend assumes API at `:9001`.
- Frontend dev assumes backend at `localhost:9001` (CRA proxy).
- Backend-to-Muninn in compose assumes `http://muninn:8000`.
- Non-compose local run examples often assume `http://127.0.0.1:8000` for Muninn and `http://127.0.0.1:8008` for host vLLM.

### Host/container mismatch risks

- `LLM_BASE_URL=http://llm:8000` works inside compose network, not on host-run backend unless overridden.
- `MUNINN_BASE_URL=http://muninn:8000` works inside compose network; host-run backend requires `127.0.0.1` or reachable hostname.
- `FRIDAY_DATA_DIR=/data` is default, but compose mounts repo at `/app`; `/data` and `/logs` are not separately volume-mounted, so persistence behavior may differ from expectation.

## Dependencies

### Python dependency sources

- Primary manifest: `requirements.txt`
- No `pyproject.toml`, no backend-local requirements manifest detected.

Key backend/runtime deps in `requirements.txt`:
- `fastapi`, `uvicorn`, `pydantic`, `httpx`
- `llama-cpp-python`, `transformers`, `torch`, `accelerate`
- test/dev tools listed (`pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `isort`, `flake8`, `mypy`)

### Node dependency sources

- Frontend manifest: `frontend/package.json` (+ `frontend/package-lock.json`)
- Root `package.json` exists but only contains devDependencies (`autoprefixer`, `postcss`, `tailwindcss`) and no scripts.
- Root `package-lock.json` also exists.

### Lockfiles present

- `frontend/package-lock.json` present
- Root `package-lock.json` present
- No `pnpm-lock.yaml` or `yarn.lock` found

## Current Run Commands and Scripts

### Backend run paths

- Local:
  - `bash start.sh` (loads `.env`, checks/kills backend port, runs `python -m backend.main`)
  - direct: `python -m backend.main`
- Container:
  - `docker compose up --build` (from README/RUNBOOK)

### Smoke and diagnostics

- `bash scripts/smoke_memory.sh`
  - checks backend health
  - chat round-trip
  - confirm flow
  - fallback behavior with unreachable Muninn

### Frontend run paths

- `cd frontend && npm start` (CRA dev server)
- `cd frontend && npm run build`
- `cd frontend && npm test`

## Tests and Quality

### Test inventory

Detected test files:
- `tests/test_agent_api.py`
- `tests/test_chat_recovery.py`
- `tests/test_coder_fallback.py`
- `tests/test_interaction_policy.py`
- `tests/test_memory.py`
- `tests/test_model_switching.py`
- `tests/test_prompt_builder.py`
- `tests/test_response_shaper.py`

### Current known-good status

```bash
$ pytest -q
..........................                                               [100%]
```

### Lint/quality command state

- Python lint/type tools are listed in `requirements.txt` (`black`, `isort`, `flake8`, `mypy`) but no centralized config (`pyproject.toml` absent) found in this inspection.
- Frontend has CRA ESLint integration via `react-scripts`, but no dedicated `lint` script is defined in `frontend/package.json`.

## Dockerization Blockers / Risks

1. Frontend toolchain ambiguity:
   - CRA scripts in use, but Vite config and Vite env files exist.
   - Dockerization must pick one canonical frontend pipeline.

2. Frontend env mismatch:
   - Active API client uses `REACT_APP_API_URL`, while local frontend `.env` currently emphasizes `VITE_*`.

3. Compose models file network assumption:
   - `docker-compose.models.yml` references `friday_net` but does not define it.

4. Persistence path mismatch:
   - Backend defaults to `/data` and `/logs`; compose currently mounts `.:/app` only.

5. Health dependency strictness:
   - `depends_on` for Muninn uses `service_started` (not `service_healthy`), potentially allowing backend start before Muninn health readiness.

6. Mixed local/compose URL assumptions:
   - Default envs differ between host mode and container mode for `MUNINN_BASE_URL` and `LLM_BASE_URL`.

7. Large repo context for docker build:
   - Local `frontend/node_modules`, `frontend/build`, `tmp/`, and logs exist in workspace.
   - Without a strict `.dockerignore`, build context size and cache invalidation can be poor.

8. Legacy tree and duplicate docs:
   - `legacy/`, multiple runbooks, and extra top-level artifacts increase ambiguity for “production source of truth.”

9. Root Node manifests ambiguity:
   - Root `package.json`/`package-lock.json` exist in addition to `frontend/` manifests, unclear deployment role.

10. Unimplemented service stubs:
   - `stt/tts/vision/avatar` API endpoints are mostly feature-gated stubs; production hardening must clearly mark expected behavior when enabled.

## Unknowns

- No explicit production ASGI process strategy beyond direct `uvicorn.run` in app module.
- No explicit frontend production-serving strategy in compose (e.g., Nginx static service) in current primary compose file.
- No documented secret management policy for production environment variables in inspected files.
- No explicit CI pipeline config was inspected in this pass.

## Recommended Dockerization Approach (No Implementation Yet)

### Option A: Single compose stack (pragmatic baseline)

- Services:
  - `backend` (FastAPI/uvicorn)
  - `frontend` (built static assets served by Nginx)
  - `muninn`
  - optional `llm` profile service
- Use multi-stage Dockerfile for frontend static bundle.
- Keep one canonical env contract with mode-specific overlays.

Best for:
- one-host deployment
- low operational complexity

### Option B: Split app compose + model compose (profiled)

- `docker-compose.app.yml`: backend + frontend + muninn + redis(optional)
- `docker-compose.models.yml`: llm/vision/stt/tts/avatar profiles
- Explicit shared external network and health-gated dependencies.

Best for:
- teams that sometimes use host-run or external model serving
- clearer model lifecycle control

### Option C: Backend API + edge proxy first, frontend static separately

- Backend container with stable `/api` contract and readiness checks.
- Frontend built and served independently (Nginx/CDN), with `REACT_APP_API_URL` bound at deploy time.
- Model services treated as external dependencies.

Best for:
- production hardening and independent deploy cadence
- scaling frontend and backend independently

## Practical next planning checkpoints

1. Decide canonical frontend build system (CRA vs Vite) before writing Dockerfiles.
2. Standardize runtime env matrix for host vs compose (LLM/Muninn URL strategy).
3. Define persistent volume mapping for `FRIDAY_DATA_DIR` and `FRIDAY_LOG_DIR`.
4. Add `.dockerignore` and trim build context inputs.
5. Decide whether model services are co-deployed or externalized by environment.
