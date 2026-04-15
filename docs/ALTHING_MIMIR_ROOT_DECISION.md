# Althing Mimir Root Decision

Date: 2026-04-15
Decision: **Yes, use Mimir at Friday root for repo cognition, with minimal explicit tooling.**

## What was verified
1. Friday already has runtime Mimir-style trace emission (telemetry, not runtime cognition):
- `backend/telemetry/mimir_trace.py`
- usage in chat runtime: `backend/core/chat_engine.py`

2. Friday root already has a `.mimir/` workspace with index DB:
- `/mnt/data/friday/.mimir/index.db` present.

3. `mimir` shell binary is not on PATH in this environment.
4. Mimir CLI is usable via Python module entrypoint from Mimir repo:
- `cd /mnt/data/Mimir && PYTHONPATH=src python3 -m mimir.cli --help`

## Why this is the right root decision
- Repeated Althing/Friday archaeology is a repo-navigation problem.
- Mimir solves retrieval/navigation for files/symbols/regions at repo scope.
- It does not replace runtime within-turn working memory (that is solved by `WorkingScratchpad`).

## Implemented root integration (this pass)
1. Added root helper script:
- `scripts/mimir_context.sh`
- Commands: `status`, `index`, `query`, `bundle`
- Uses `/mnt/data/Mimir` + `python3 -m mimir.cli` with `--repo /mnt/data/friday`

2. Added Makefile entrypoints:
- `make mimir-status`
- `make mimir-index`
- `make mimir-query TASK='...'`
- `make mimir-bundle TASK='...'`

## What this solves
- Fast reproducible repository cognition from Friday root.
- Standardized invocation path for developers/agents.
- Removes dependence on ad hoc command memory for Mimir operations.

## What this does not solve
- It does not add runtime conversational memory.
- It does not add within-turn private reasoning memory.
- It does not alter Althing answer synthesis behavior directly.

## Operational notes
- Integration is optional and non-blocking.
- If `/mnt/data/Mimir` is unavailable, script exits with explicit actionable error.
- No runtime path now depends on Mimir availability.
