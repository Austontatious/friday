# ALTHING Memory Next Step Recommendation

Date: 2026-04-14

## Single best next implementation move

Introduce a **bounded private `WorkingScratchpad` object inside Althing execution** (in `/mnt/data/althing/router/main.py`), and require final answer synthesis to read from that scratchpad instead of free-form lane output concatenation.

## Why this is the right next move

1. It directly targets the missing behavior.
   - Current code has transient orchestration state (`ExecutionState`) but no first-class private whiteboard contract.

2. It is the smallest high-leverage step.
   - Reuses existing request lifecycle and lane workflow scaffolding.
   - Does not require immediate redesign of durable memory, retrieval infra, or client protocol.

3. It improves reasoning quality without broad architecture churn.
   - Adds explicit intermediate structure for assumptions/evidence/open-questions/final-claim alignment.
   - Keeps internals private to runtime flow.

## Reuse existing components

1. Reuse `ExecutionState` lifecycle and step recording.
   - Current anchoring points: `/mnt/data/althing/router/main.py:89-101`, `:257-285`, `:2334-2472`.

2. Reuse existing synthesis step boundaries.
   - Existing workflows already have explicit synthesize phases (`_workflow_*_synthesize` + direct lane path).

3. Reuse existing output sanitation and quality checks.
   - Keep current final-output hygiene/quality gates unchanged.

## Do not attempt yet

1. Do not redesign Muninn or add new durable-memory schemas in this step.
2. Do not merge Direct Friday and Althing memory architectures in one pass.
3. Do not expand to cross-session memory behavior in the same change.
4. Do not expose scratchpad content in response payloads or telemetry logs.

## Minimal acceptance criteria for this next step

1. A per-request scratchpad object exists with fixed bounded fields (no unbounded append).
2. Lane/tool intermediate signals are normalized into scratchpad fields.
3. Final synthesis consumes scratchpad and emits user-facing response only.
4. Scratchpad is excluded from API response bodies and trace payload content (only aggregate counters allowed).
