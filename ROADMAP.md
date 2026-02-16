# ROADMAP

## 2026-02-16 Snapshot
- Completed: FRIDAY memory cutover to external Muninn via `MemoryProvider` (`muninn|legacy|none`).
- Completed: chat pipeline pre-prompt rehydrate + post-response stage flow.
- Completed: minimal web confirmation UX (Accept all / Reject all) and backend relay endpoints.
- Completed: graceful fallback to legacy/no-memory when Muninn is unavailable.

## Next
- Add per-item memory confirmation UI.
- Add richer candidate extraction beyond conservative heuristics.
- Add automated backend API tests for memory relay endpoints.
