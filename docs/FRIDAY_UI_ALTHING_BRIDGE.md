# Friday UI -> Althing Bridge

## Purpose

Use the existing Friday frontend as the user shell while making Althing the default orchestration entry point.

Flow:

`User -> Friday UI -> Althing -> (local lanes / Friday handoff as needed) -> Friday UI`

## UI Modes

The frontend exposes two explicit modes:

- `Althing` (default): sends requests to `POST /api/althing/chat`.
- `Direct Friday`: sends requests to `POST /api/chat`.

Mode selection is persisted in local storage (`friday_chat_mode`).

## Backend Bridge Route

Friday backend route:

- `POST /api/althing/chat`

Behavior:

- validates prompt input
- prepends a Friday system layer message (mode=`althing_routed`) unless caller already provides a system message
- forwards to Althing `chat/completions` endpoint for normal routed prompts
- detects local path / repo file prompts and falls back to direct Friday read-only workspace inspection instead of sending those prompts into Althing-only lanes
- if the upstream router reports `no_routable_lane_available` or `state_unavailable`, falls back to direct Friday chat instead of surfacing the upstream failure
- normalizes result into existing frontend response shape (`assistant_text`, `text`, `meta`)
- preserves existing `POST /api/chat` behavior for direct mode

## Recursion Prevention

Bridge route explicitly rejects potential handoff recursion:

- if `X-Althing-Handoff: 1` is present (or handoff-shaped payload markers), `/api/althing/chat` returns `409 recursion_guard`
- Althing execution/handoff traffic should use Friday's dedicated `POST /api/handoff` path

Althing now marks execution requests to Friday with `X-Althing-Handoff: 1`.

## Config

Friday bridge flags:

- `FRIDAY_ALTHING_BRIDGE_ENABLED`
- `FRIDAY_ALTHING_BASE_URL`
- `FRIDAY_ALTHING_ROUTE_PATH`
- `FRIDAY_ALTHING_TIMEOUT_MS`
- `FRIDAY_ALTHING_MODEL_HINT`
- `FRIDAY_ALTHING_MODEL_CLASS` (prompt lane class for routed bridge system layer)
- `FRIDAY_FILE_SEARCH_EXTRA_ROOTS`
- `FRIDAY_UI_DEFAULT_MODE`

Runtime mount:

- app compose now mounts `/mnt/data` into `friday-backend` as read-only so direct Friday path inspection can resolve host workspace paths without enabling writes

## Validation Targets

- Althing mode from UI works (`/api/althing/chat`)
- Direct Friday mode still works (`/api/chat`)
- mode switching works in frontend
- handoff recursion guard blocks `X-Althing-Handoff` at bridge route
