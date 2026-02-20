# ROADMAP

## 2026-02-16 Snapshot
- Completed: FRIDAY memory cutover to external Muninn via `MemoryProvider` (`muninn|legacy|none`).
- Completed: chat pipeline pre-prompt rehydrate + post-response stage flow.
- Completed: minimal web confirmation UX (Accept all / Reject all) and backend relay endpoints.
- Completed: graceful fallback to legacy/no-memory when Muninn is unavailable.
- Completed: Muninn client hardening (timeouts/retries/API-key headers) with provider-level fallback telemetry.
- Completed: guardrails for memory injection size and confirm endpoint input validation caps.
- Completed: compose baseline now runs `friday-backend` + `muninn` with non-blocking startup dependency.

## Next
- Add per-item memory confirmation UI and reason display.
- Add richer candidate extraction beyond conservative heuristics.
- Add integration tests against a live Muninn container for confirm-required edge cases.
