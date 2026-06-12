# Friday Online Runtime Report

Date: 2026-06-12
Host: `unix-X10SLH-N6-ST031`
Branch: `phase0-stabilize`
Commit: `90731c9`

## What Friday Is

Friday is the local orchestration backend and UI stack under `/mnt/data/friday`. It provides:

- a direct chat runtime at `POST /api/chat`
- an Althing bridge at `POST /api/althing/chat`
- memory / trace / refinement plumbing
- a frontend served by the Friday compose stack
- a local model bridge that fans out to the live model servers through `local_llm_gateway`

In practical terms, Friday is not the model itself. It is the control layer that:

- builds prompts
- decides which lane to use
- talks to the local gateway or fallback servers
- normalizes responses into the frontend/API shape

## What It Does

Friday currently supports two user-facing paths:

1. Direct Friday chat
   - `POST /api/chat`
   - runs the local Friday chat engine
   - uses Friday memory, prompt assembly, and lane routing
   - talks to the model bridge through `LLM_BASE_URL`

2. Althing bridge chat
   - `POST /api/althing/chat`
   - forwards routed chat requests to the Althing router on `http://localhost:8010/chat/completions`
   - falls back to direct Friday for repo/file prompts that should be handled locally
   - normalizes the upstream response back into `assistant_text`, `text`, and `meta`

## How It Does It

### Direct Friday path

The direct runtime assembles a structured system prompt, recent transcript, memory overlays, and tool context before calling the configured model endpoint.

Relevant wiring:

- prompt assembly and lane selection: `backend/core/prompt_builder.py`
- chat execution and memory/runtime orchestration: `backend/core/chat_engine.py`
- durable memory provider: `backend/memory/*`
- HTTP endpoint: `backend/api/chat.py`

The direct path is model-aware. It uses:

- `FRIDAY_MODEL_NAME` for the primary lane name
- `LLM_BASE_URL` for the OpenAI-compatible endpoint
- `FRIDAY_CODER_*` variables for the coder lane when enabled

### Althing bridge path

The Althing bridge builds an Althing-routed prompt and POSTs it to the upstream router. The bridge logic lives in:

- `backend/api/althing_chat.py`

The bridge:

- validates prompt and identity
- rejects recursion markers such as `X-Althing-Handoff: 1`
- builds an Althing-specific system prompt
- forwards the request to the router upstream
- converts the upstream `choices[0].message.content` back into Friday's response envelope

If the prompt looks like repo/file work, the bridge bypasses the router and falls back to direct Friday read-only handling instead.

## How It Runs

### Current validated runtime

The validated runtime is a host-run Friday backend on port `9001` with gateway/model URLs pointed at the local host network:

- backend: `http://127.0.0.1:9001`
- local gateway: `http://127.0.0.1:8130`
- primary model backend: `http://127.0.0.1:8174/v1`
- coder model backend: `http://127.0.0.1:8176/v1`
- Muninn service: `http://127.0.0.1:8000`

That host-run backend was necessary because the compose-based Friday backend could not reach `host.docker.internal:8130` from inside the container during this session.

### Boot script behavior

`scripts/friday_up.sh` now does the following:

- probes the host gateway first
- prefers the gateway aliases `friday` and `friday-coder`
- writes `.env.runtime`
- enables Friday LLM flags when a model is discovered
- brings up the Friday app stack
- starts the model stack only when the compose gateway path is needed

This makes the runtime prefer the live local gateway instead of stale legacy model URLs.

## How It Is Connected To The Model(s)

Friday is connected to the models through the local gateway at `8130`.

The gateway contract observed in this session is:

- `friday` -> `127.0.0.1:8174/v1`
- `friday-heavy-lite` -> `127.0.0.1:8174/v1`
- `friday-coder` -> `127.0.0.1:8176/v1`
- `friday-heavy`, `chef`, `friday-fast` -> gateway-managed aliasing

Friday's runtime model wiring after the fix:

- `LLM_BASE_URL=http://host.docker.internal:8130/v1` in the runtime env when running inside compose
- `FRIDAY_MODEL_NAME=friday`
- `FRIDAY_CODER_ENABLED=1`
- `FRIDAY_CODER_BASE_URL=http://host.docker.internal:8130/v1`
- `FRIDAY_CODER_MODEL_NAME=friday-coder`

The host-run backend used direct host URLs instead:

- `LLM_BASE_URL=http://127.0.0.1:8130/v1`
- `FRIDAY_CODER_BASE_URL=http://127.0.0.1:8130/v1`

## Runtime Inventory

### Confirmed healthy

- `local_llm_gateway` on `127.0.0.1:8130`
- primary model backend on `127.0.0.1:8174`
- coder model backend on `127.0.0.1:8176`
- host-run Friday backend on `127.0.0.1:9001`
- Muninn service on `127.0.0.1:8000`

### Still present but not part of the validated runtime

- compose Friday backend on `19001 -> 9001`
- compose Friday frontend on `18080`
- compose Muninn on `18000`

### Known bridge limitation

- container-to-host access from the compose Friday backend to `host.docker.internal:8130` timed out
- host-to-host access to the gateway worked
- the Althing router on `8010` is reachable, but its router status was degraded

## Checks

### Gateway and model checks

- `GET http://127.0.0.1:8130/health` returned healthy
- `GET http://127.0.0.1:8130/v1/models` exposed the public aliases
- `GET http://127.0.0.1:8174/v1/models` returned the q4 model backend
- `GET http://127.0.0.1:8176/v1/models` returned the coder model backend

### Friday direct runtime checks

- `GET /healthz` on `http://127.0.0.1:9001` returned `{"ok": true}`
- `GET /readyz` returned healthy for `llm`, `coder`, and `memory`
- `POST /api/chat` with a simple prompt returned `runtime-chat-ok.`
- `POST /api/chat` with `use_coder_model=true` returned `coder-route-ok`

### Althing bridge checks

- `POST /api/althing/chat` now returns a normal Friday response shape for the smoke prompt
- upstream Althing router still reports `degraded` with `exec`, `coder`, and `reason` as `state_unavailable`
- Friday bridge now degrades into direct Friday chat when that upstream condition is detected

## Fixes Applied

1. Updated `scripts/friday_up.sh`
   - detects the local gateway first
   - prefers the live `friday` and `friday-coder` aliases
   - writes a cleaner `.env.runtime`
   - enables the Friday model flags when the gateway is present
   - avoids the stale `Lexi` / `host.docker.internal:8008` default for this runtime

2. Brought up a host-run Friday backend on port `9001`
   - used direct host URLs to avoid the compose bridge failure
   - validated both primary and coder chat routes

3. Cleaned the runtime report location itself
   - replaced the placeholder file with an actual operational report

## Final Status

Friday is online and validated on the host-run backend path, including the Althing bridge fallback.

Validated:

- gateway connectivity
- primary Friday model routing
- coder model routing
- direct Friday health/readiness/chat
- Althing bridge fallback to direct Friday on `no_routable_lane_available`

Residual issue:

- the upstream Althing router remains degraded, but Friday no longer surfaces that as a user-facing bridge failure

Operationally, the main Friday runtime is usable and the Althing bridge now degrades cleanly into direct Friday when the upstream router is unavailable.

## Althing Bridge Fix Pass

Starting state:

- Direct `/api/chat` passes.
- Explicit coder `/api/chat` passes.
- `/api/althing/chat` started with `no_routable_lane_available`.
- Gateway routing was left unchanged.

Fix applied:

- `backend/api/althing_chat.py` now detects upstream lane-unavailable responses and falls back to `run_chat()` instead of surfacing the upstream error.
- The bridge still preserves the existing repo/file direct-fallback path.
- Metadata now records the degraded bridge path through `bridge_fallback` and `bridge_fallback_reason`.

Validation:

- `POST /api/althing/chat` with a lane-unavailable upstream response returns a normal Friday response shape.
- `POST /api/chat` still returns the working direct Friday response shape.
