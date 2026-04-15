# Althing Working Memory vs Mimir Boundary

Date: 2026-04-15

## Purpose
Prevent architecture drift by keeping runtime cognition, durable memory, and repo cognition separated.

## Layer boundaries

| Layer | Purpose | Lives where | Lifetime | Consumers | Must not be used for |
|---|---|---|---|---|---|
| Runtime WorkingScratchpad | Within-turn private cognition and synthesis scaffolding | `/mnt/data/althing/router/working_scratchpad.py` + `ExecutionState` | Single request/turn | Althing routing + synthesis in `_execute` | Cross-turn persistence, repo indexing, durable user profile memory |
| Conversational/Durable memory | Cross-turn recall and persistence (transcript + provider-backed cards/candidates) | Friday direct runtime (`backend/core/chat_engine.py`, `backend/memory/*`) | Session to durable store | Direct Friday chat/memory APIs | Within-turn hidden whiteboard, repo-topology navigation |
| Repo cognition (Mimir) | Repo file/symbol/region navigation for developer/agent workflows | Friday root `.mimir/` + `/mnt/data/Mimir` CLI tooling | Persistent index refreshed by indexing runs | Humans/agents during development and investigation | Runtime answer working memory, user conversation memory |

## Data handling constraints
- `WorkingScratchpad` content is private-by-default and excluded from normal final answer.
- Durable memory writes should not serialize scratchpad internals.
- Mimir index data should not be treated as user/session memory.

## Current integration map
1. WorkingScratchpad: integrated into Althing live routing path and synthesis.
2. Durable memory: active in direct Friday path, not in Althing bridge path by default.
3. Mimir: available for repo cognition through root script/Makefile targets; runtime telemetry remains env-gated.

## Guardrail statement
Any future feature proposal must declare which layer it belongs to. A feature cannot be accepted if it mixes these layers without explicit contract updates.
