# FRIDAY Decisions

## D-001: Memory Provider Abstraction
- Date: 2026-02-16
- Decision: Keep memory behind a provider interface (`muninn|legacy|none`) instead of coupling chat runtime directly to one store.
- Why: enables external memory evolution without destabilizing core chat runtime, and supports deterministic fallback paths.

## D-002: Stage + Confirm Workflow
- Date: 2026-02-16
- Decision: Use `rehydrate -> stage_candidates -> confirm_candidates` flow with browser confirmation through FRIDAY relay endpoints.
- Why: sensitive candidate writes should be explicitly user-confirmed; browser should not access Muninn directly.
- API boundary:
  - `POST /api/memory/confirm`
  - `POST /api/memory/pending`

## D-003: Memory Failures Must Not Break Chat
- Date: 2026-02-16
- Decision: Treat memory provider failures as degradations, not fatal request errors.
- Why: product reliability priority is uninterrupted chat response.
- Runtime behavior:
  - log fallback reason + provider switch
  - continue with fallback provider (`legacy` then `none` by default)
  - always return chat response payload
