# FRIDAY

FRIDAY is a modular assistant backend with safe degradation rules:
- chat must keep working even when optional services fail
- memory is provider-driven and must never take chat down
- multimodal services stay feature-flagged

## Current Runtime (2026-02)
- Text chat via `POST /api/chat`
- Async agent runs via `POST /api/agent` + `POST /api/agent/wait`
- Tool parsing/execution with trust + confirmation gates
- Identity middleware with stable entity id resolution
- External memory provider abstraction: `muninn | legacy | none`
- Pre-turn memory rehydrate into `<SYSTEM_MEMORY>` and post-turn candidate staging
- Confirmation relay endpoints:
  - `POST /api/memory/confirm`
  - `POST /api/memory/pending`

## Quick Start (FRIDAY + Muninn)
```bash
cp .env.example .env
docker compose up --build
```

By default this brings up:
- `friday-backend` on `http://localhost:9001`
- `muninn` on `http://localhost:8000`

If Muninn is unavailable, FRIDAY falls back to `legacy` (or `none`) and still returns chat responses.

## Docker (Dev / Prod)

Dev (backend + muninn):
```bash
docker compose -f docker-compose.dev.yml up --build
# run frontend on host for speed:
cd frontend && npm start
```

Prod-like app stack:
```bash
docker compose -f docker-compose.app.yml up --build -d
```

One command (autodiscover host Muninn/LLM, else start containers):
```bash
./scripts/friday_up.sh
```

Override examples:
```bash
HOST_LLM_URL_DEFAULT=http://127.0.0.1:8008 ./scripts/friday_up.sh
AUTO_START_MODELS=0 ./scripts/friday_up.sh
```

Example: avoid port conflicts on a busy host:
```bash
FRIDAY_HOST_API_PORT=19001 FRIDAY_HOST_WEB_PORT=18080 FRIDAY_HOST_MUNINN_PORT=18000 \
docker compose -f docker-compose.app.yml up --build -d
```

With models:
```bash
docker compose -f docker-compose.app.yml up --build -d
docker compose -f docker-compose.models.yml up -d
```

Or single command:
```bash
docker compose -f docker-compose.app.yml -f docker-compose.models.yml up --build -d
```

Default endpoints:
- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:9001`
- Muninn: `http://localhost:8000`

## Identity / `entity_id` Priority
FRIDAY resolves stable identity in this order:
1. `X-Friday-Account-User` (or `X-Authenticated-User`)
2. `X-Friday-Session` header, then `friday_session` cookie
3. `X-Friday-Device` header, then `friday_device` cookie
4. Local dev fallback: `ent_local_user`

`request.state.user_id` is used as the `entity_id` for memory operations.

## Response Contract
`POST /api/chat` returns:

```json
{
  "assistant_text": "...",
  "text": "...",
  "meta": {
    "llm_route": "primary",
    "interaction_mode": "focused|neutral|warm",
    "certainty_level": "high|medium|low"
  },
  "memory": {
    "provider": "muninn",
    "accepted_ids": [],
    "pending_ids": [],
    "pending_reasons": [],
    "rejected": 0
  }
}
```

`memory.provider` reflects the provider actually used at runtime (`muninn`, `legacy`, or `none`), including fallback cases.

## Memory Provider Config
Core:
- `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none` (default: `muninn`)
- `FRIDAY_MEMORY_FALLBACK_PROVIDER=legacy|none` (default: `legacy`)
- `MUNINN_BASE_URL` (default in `.env.example`: `http://muninn:8000`; for non-compose local runs use `http://127.0.0.1:8000`)
- `MUNINN_NAMESPACE=friday`
- `MUNINN_PROFILE=friday`

Security:
- `MUNINN_REQUIRE_API_KEY=0|1`
- `MUNINN_API_KEY=...`
- `MUNINN_READONLY=0|1`

Timeout/retry:
- `MUNINN_CONNECT_TIMEOUT_SECONDS` (default `2`)
- `MUNINN_READ_TIMEOUT_SECONDS` (default `5`)
- `MUNINN_HTTP_OVERALL_TIMEOUT_SECONDS` (default `7`)
- `MUNINN_HTTP_RETRIES` (default `1`)
- `MUNINN_HTTP_RETRY_BACKOFF_SECONDS` (default `0.2`)

Guardrails:
- `FRIDAY_MEMORY_MAX_INJECT_CARDS`
- `FRIDAY_MEMORY_MAX_INJECT_BULLETS`
- `FRIDAY_MEMORY_MAX_INJECT_CHARS`
- `FRIDAY_MEMORY_MAX_INJECT_TOKENS`
- `FRIDAY_MEMORY_CONFIRM_MAX_IDS`
- `FRIDAY_MEMORY_CONFIRM_MAX_ID_LEN`
- `FRIDAY_MEMORY_CONFIRM_MAX_NOTE_CHARS`
- `FRIDAY_DEBUG_MEMORY=1` to log injected `<SYSTEM_MEMORY>` block (truncated)
- `FRIDAY_DEBUG_PROMPT=1` to log composed system prompt diagnostics
- `FRIDAY_DEBUG_PROMPT_MAX_CHARS=2000` for prompt debug head/tail clipping
- `FRIDAY_SYSTEM_PROMPT_MAX_CHARS=16000` hard cap after optional memory append

## LLM Model Config (vLLM)
- `FRIDAY_MODEL_NAME=Lexi` (default)
- `LLM_BASE_URL=http://llm:8000` when using compose `llm` service
- `LLM_BASE_URL=http://127.0.0.1:8008` when backend runs on host against host vLLM
- Optional coding specialist route (fallback to primary on failure):
  - `FRIDAY_CODER_ENABLED=1`
  - `FRIDAY_CODER_MODEL_NAME=...`
  - `FRIDAY_CODER_BASE_URL=...`
  - `FRIDAY_CODER_API_KEY=...` (optional)
  - Activate per request with `agent_profile: "coding"` or `use_coder_model: true`

## Interaction Policy (v1)
- Rule-based interaction modes: `focused`, `neutral`, `warm`.
- `playful` is hard-gated and only available when:
  - `FRIDAY_INTERACTION_PLAYFUL_ENABLED=1`
  - user explicitly requests it in-session.
- Env:
  - `FRIDAY_INTERACTION_DEFAULT_MODE=neutral`
  - `FRIDAY_INTERACTION_ONE_SCREEN_CHARS=900`
  - `FRIDAY_INTERACTION_PLAYFUL_ENABLED=0`
- User override phrases:
  - `be brief` -> focused
  - `be human` -> warm
  - `no banter` -> banter budget forced to zero
- Deterministic shaping enforces one-question cap and one-screen default.

## Smoke Test
```bash
bash scripts/smoke_memory.sh
```

This validates:
- FRIDAY health and chat response
- `memory.provider` present in chat response
- confirm relay path (`/api/memory/confirm`)
- graceful fallback behavior when Muninn is unreachable

## Notes
- LLM stays optional (`FRIDAY_LLM_ENABLED=0` by default).
- Multimodal endpoints remain feature-flagged/stubbed.
- See `docs/RUNBOOK.md` for manual checks and fallback triage.
- See `docs/DECISIONS.md` for architecture decisions.
