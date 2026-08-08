# ADR 003: SketchMath feature-gate contract

## Problem

SketchMath had contradictory implicit defaults: the backend rejected requests when `FRIDAY_SKETCHMATH_ENABLED` was unset, while the frontend displayed the workspace when `REACT_APP_SKETCHMATH_ENABLED` was unset. A default deployment could therefore advertise a workspace whose API was disabled.

## Options considered

1. Default both frontend and backend on because the current MVP is functional.
2. Default both off and require explicit enablement in source, local development, tests, and production builds.
3. Add a runtime frontend capability probe and remove the frontend build flag immediately.

## Decision

- SketchMath defaults off at both boundaries.
- Backend truthy values match the shared config convention: `1`, `true`, `yes`, or `on`.
- Frontend build-time truthy values use the same set.
- A usable deployment must set both `FRIDAY_SKETCHMATH_ENABLED=1` and `REACT_APP_SKETCHMATH_ENABLED=1`.
- Compose and the frontend Dockerfile declare explicit default-off values; browser acceptance explicitly enables both.
- A future runtime capability handshake may replace the build-time frontend flag, but it is not part of Gate A.

## Rationale

- This follows the repository rule that new features are default off unless required for the baseline.
- It prevents the frontend from claiming an unavailable backend capability.
- It keeps current deployments reversible without changing API routes or session data.

## Consequences

- Existing environments that relied on the frontend's implicit-on behavior must set the frontend flag explicitly and rebuild the static bundle.
- Backend-only enablement does not expose a navigation entry; frontend-only enablement renders a direct-route disabled message instead of a working workspace.
- Local E2E remains deterministic because its launcher sets both flags.

## Boundary ownership

- Backend flag owner: `core/config.py` and the SketchMath API boundary.
- Frontend flag owner: `frontend/src/services/sketchmath.ts` and frontend build configuration.
- Deployment compatibility owner: FRIDAY Compose and `.env.example`.

## Rollback

Revert this ADR's implementation commit and rebuild the frontend. No data or schema migration is involved.

## Explicit deferrals

- Runtime capability discovery for the static frontend.
- Per-user or per-tenant SketchMath authorization.
