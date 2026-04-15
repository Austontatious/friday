# Althing Scratchpad Live Eval + Restart + End-of-Night Push Report

Date: 2026-04-15

## Services restarted

### Althing path
- Why restart: live scratchpad runtime code changed in `/mnt/data/althing/router/*`; router image must be rebuilt/recreated to load new code.
- Command used:
  - `cd /mnt/data/althing && docker compose up -d --build --no-deps router`
- Evidence:
  - container `althing_router` start time changed:
    - before: `2026-04-13T03:12:45.03246901Z`
    - after:  `2026-04-15T02:07:57.221221237Z`

### Friday path
- Why restart: bridge runtime path is served by Friday backend (`/api/althing/chat`) and needed explicit bounce confirmation.
- Commands used:
  - build attempt: `cd /mnt/data/friday && docker compose -f docker-compose.app.yml up -d --build --no-deps friday-backend friday-frontend`
  - forced bounce: `cd /mnt/data/friday && docker compose -f docker-compose.app.yml up -d --force-recreate --no-deps friday-backend friday-frontend`
- Evidence:
  - `friday-friday-backend-1` start time changed:
    - before recreate: `2026-04-15T01:57:27.765349608Z`
    - after recreate:  `2026-04-15T02:08:27.53495498Z`
  - `friday-friday-frontend-1` start time changed:
    - before recreate: `2026-04-14T22:01:27.144051596Z`
    - after recreate:  `2026-04-15T02:08:33.926757999Z`

## Health verification after restart

- Althing health:
  - `GET http://127.0.0.1:8010/healthz?profile=control_phase1`
  - Result: `status=ok`, exec/coder/reason lanes all `ready=true`.
- Friday health:
  - `GET http://127.0.0.1:9001/healthz` -> `{ "ok": true }`
- Friday ready:
  - `GET http://127.0.0.1:9001/readyz` -> `{ "ok": true }`, backend reports LLM/coder healthy.
- Bridge smoke check:
  - `POST http://127.0.0.1:9001/api/althing/chat` with prompt `Reply with exactly: bridge_alive`
  - Result: `assistant_text=bridge_alive`.

## Proof scratchpad path is live

Probe call:
- `POST http://127.0.0.1:8010/route` with `evaluation_trace=true`.

Observed:
- `has_debug_step=true` for `debug_working_scratchpad_snapshot` in `outputs.intermediate`.
- `synthesis_used=true`.
- `scratchpad_leak_in_final=false`.

Conclusion:
- Scratchpad path is **definitely live**.

## Live outcome evaluation (scratchpad-sensitive prompts)

Endpoint used (user path):
- `POST http://127.0.0.1:9001/api/althing/chat`

Artifact outputs:
- Raw: `/mnt/data/friday/artifacts/althing_scratchpad_live_eval_20260415T021340Z.json`
- Summary: `/mnt/data/friday/artifacts/althing_scratchpad_live_eval_20260415T021340Z.md`

Prompt set:
1. research analysis (event sourcing go/no-go)
2. design critique (single `/execute` API)
3. multi-part conceptual (optimistic vs pessimistic concurrency)
4. debugging/planning (502 + DB pool saturation)
5. coding architecture/planning (monolith split in 6 weeks)

Run result:
- success: `5/5`
- failures: `0/5`
- explicit scratchpad/think-tag leakage incidents: `0`

## Outcome comparison (operator-readable)

Compared against prior failure modes (visible scratchpad leakage, rambling exploratory narration, weak synthesis):

| Prompt | Scratchpad leakage | Synthesis structure | Directness | Completeness | Notes |
|---|---|---|---|---|---|
| research_analysis | none | strong | strong | strong | Clear thesis + risks + mitigations + recommendation. |
| design_critique | none | medium | medium | strong | Still contains visible self-narration opener (“Okay, let's tackle…”), though no private-scratch leakage. |
| multi_part_conceptual | none | medium | strong | medium | Correct but compact; exception handling could be sharper/structured. |
| debug_planning | none | strong | strong | strong | Structured plan + causes + rollback criteria. |
| coding_arch_planning | none | strong | strong | strong | Phase plan + boundaries + checkpoints present. |

## Outcome judgment

Classification: **`mixed_improvement`**

What improved:
- No visible scratchpad markers or think tags across evaluated prompts.
- Better synthesis consistency in planning/debug/architecture prompts.
- Answers generally more directly user-facing and structured.

What did not fully improve:
- Some prompts still show mild conversational self-narration and meta lead-ins.
- Structure quality is uneven (notably design critique / conceptual prompt).

Most important remaining issue:
- Tighten final synthesis discipline to suppress non-essential preamble/meta narration while preserving depth.

## Repos committed/pushed

### `/mnt/data/althing`
- Git status: no git repository detected at this path.
- Commit/push status: **blocked** (cannot commit/push without repository metadata).

### `/mnt/data/friday`
- Branch: `phase0-stabilize`
- Commit hash: `TBD_AFTER_COMMIT`
- Push status: `TBD_AFTER_PUSH`
- Commit scope policy: only scratchpad/mimir decision/eval report related files (no broad unrelated tree sweep).

## Blockers/caveats

- `/mnt/data/althing` is currently not a git repo in this environment; push is impossible there unless a canonical VCS root is provided.
- Friday working tree contains extensive unrelated pre-existing changes; this wrap-up commits only the cohesive scratchpad/mimir/eval reporting subset.
