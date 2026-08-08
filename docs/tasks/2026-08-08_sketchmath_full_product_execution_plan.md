# SketchMath Full Product Execution Plan — 2026-08-08

## Scope

Evolve the validated SketchMath MVP into the product defined by `docs/sketchmath/product_spec.md` through reversible, evidence-backed slices. This plan is execution guidance; the product spec and traceability ledger are canonical.

## Dependency Order

1. Preserve and stabilize contracts, docs, gates, build, and validated history.
2. Define the canonical parametric document and solver boundaries before broad geometry growth.
3. Deliver a defensible parametric sketcher before general planar topology.
4. Build feature history before relying on downstream topological references.
5. Add multi-sketch/model-tree/document semantics on the stable feature model.
6. Add model-aware AI only over typed canonical operations.
7. Harden with adversarial, performance, deployment, and recovery evidence.

## Phase 0 — Gate A

### Slice A1: canonical spec and contradiction ledger

Artifacts:

- `docs/sketchmath/product_spec.md`
- `docs/sketchmath/traceability.md`
- `docs/sketchmath/status.md`
- this execution plan

Acceptance: requirements, exclusions, contradictions, baseline evidence, and gate states are explicit.

### Slice A2: command and state contract reconciliation

Update runtime models, JSON schemas, frontend command types, command catalog, UI docs, contract tests, and relevant eval declarations so the implemented v0.1/v0.2 envelope is one coherent contract.

Acceptance: declared/implemented command and entity/constraint sets match; unsupported versions/commands fail structurally; existing commands remain compatible.

### Slice A3: feature gate and build cleanup

Choose one default-off SketchMath contract consistent with repository policy, test frontend/backend unset/off/on behavior, remove unused SketchMath state, and avoid broad dependency churn for non-SketchMath warnings.

Acceptance: no frontend/backend disagreement and no SketchMath source warning in production build.

### Slice A4: full regression and checkpoint

Run the audited baseline plus contract additions, inspect diff/status, update durable project memory, and commit small coherent slices.

### Slice A5: deliberate remote landing

Enumerate the transitive commit/file dependencies of the 24 SketchMath commits. Prefer a dedicated remotely published product branch or a reconstructed/cherry-picked baseline only when it preserves runtime/build dependencies without importing unrelated product work. Record remote ref, commit, validation, and rollback. Never force-push.

## Phase 1 — Gate B

### Architecture checkpoint

Write ADRs for:

- canonical document/model schema and migration boundary;
- solver interface, supported equation families, DOF semantics, tolerances, and external-library licensing implications;
- async solve/rebuild boundary when operations exceed interactive request budgets.

### Initial implementation sequence

1. Centralized tolerances and explicit units.
2. Solver analysis result model with honest `partial`/`unknown` coverage.
3. Defensible point/line/circle DOF subset and conflict diagnostics.
4. Radius/diameter and horizontal/vertical distance constraints.
5. Arc entity and typed commands after the model/solver contract can support it.
6. Mixed-geometry browser acceptance with reload-stable solver state.

## Later Phases

- Phase 2: general planar-region topology and adversarial profile selection.
- Phase 3: canonical feature graph, add/cut/revolve/hole/edge operations, rebuild.
- Phase 4: semantic topological references and repairable ambiguity.
- Phase 5: multi-sketch planes, model tree/property editor, CAD-grade viewport.
- Phase 6: versioned document persistence, concurrency, recovery, artifact lifecycle.
- Phase 7: model-aware AI proposal/planning over typed operations.
- Phase 8: deterministic and heuristic design review with clear labels.
- Phase 9: adversarial, performance, observability, deployment, and recovery hardening.

## Validation Policy

Each slice records:

- requirement IDs;
- changed implementation and contract surfaces;
- unit/API/geometry/solver/topology/frontend/eval/browser checks run;
- geometric artifact evidence where applicable;
- commit hash;
- rollback path and open limitations.

Unavailable live-runtime evidence remains explicitly untested; scaffolding never counts as a passed product gate.

## Stop Conditions

Stop and request direction only for a major architectural fork, threatening license implication, destructive migration, credential/secret need, unsafe deployment, or inability to establish geometric correctness.
