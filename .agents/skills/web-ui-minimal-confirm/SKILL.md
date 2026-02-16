# Skill: web-ui-minimal-confirm

## Objective
Expose a minimal confirmation flow for pending memory items.

## Backend Contract
- `POST /api/memory/confirm`
- `POST /api/memory/pending` (optional)

## Frontend Contract
- If `memory.pending_ids.length > 0`, show a compact banner.
- Buttons only: `Accept all` and `Reject all`.
- Display lightweight success/error toast.

## Rules
- Keep UI additive and low-risk.
- Avoid per-item editing unless explicitly requested.
