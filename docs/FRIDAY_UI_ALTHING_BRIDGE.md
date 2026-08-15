# Retired: Friday UI Althing bridge

The Althing bridge was removed from Friday on 2026-08-15 as part of Althing's
retirement. Friday now has one chat mode and sends UI requests to `POST /api/chat`.

Removed operational surfaces include the `/api/althing/chat` route, bridge
environment variables, Althing Docker network membership, bridge prompt/config
code, and bridge-specific doctors. Historical reports elsewhere under `docs/`
remain dated evidence and must not be used as deployment instructions.

Friday may consume the independently operated `exec` and `coder` OpenAI-compatible
model endpoints. Startup and doctors require exact served model identities; a
reachable port with the wrong model is a hard failure.
