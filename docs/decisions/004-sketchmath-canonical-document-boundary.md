# ADR 004: SketchMath canonical document and migration boundary

Status: accepted; v1 compatibility envelope implemented behind a default-off flag

Date: 2026-08-08

## Problem

`SelectionContext` currently serves as API selection payload, persisted sketch state, solver input, and the effective product document. Extrusion produces an artifact in operation metadata but does not persist a feature. Whole before/after snapshots provide undo, while replay re-executes commands and can therefore repeat external CAD work.

That shape cannot safely own multiple sketches, bodies, feature dependencies, revisions, artifact lineage, or stable downstream references.

## Decision

- SketchMath will own a versioned document envelope above the existing sketch state.
- The document owns immutable IDs, user-facing names, units, revision, bodies, sketches, features, dependencies, artifacts, and provenance.
- `SelectionContext` remains the compatibility representation of one sketch during migration; it does not become the multi-body document model.
- Operations target a document revision and produce a pure proposed document patch before commit.
- Feature rebuild is deterministic and ordered by explicit dependencies. Kernel execution consumes a rebuild request but never owns canonical IDs or feature history.
- Undo/redo records canonical model operations or patches. Replaying model history must not repeat exports, filesystem writes, or other external side effects.
- Topological references will use semantic source IDs plus geometric signatures and recovery state; raw FreeCAD face/edge indices are never public contracts.

## Migration boundary

1. A versioned reader continues accepting current session JSON.
2. Legacy state is wrapped as one document, one body, and one sketch without changing existing entity IDs.
3. `FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED` enables dual-read/new-write behavior for the accepted one-sketch compatibility envelope. It remains default off while broader migration/golden fixtures are open.
4. Destructive in-place migration is prohibited. Original session files remain recoverable until the new format passes reload and rollback gates.

## Consequences

- Phase 1 solver work can continue against `SelectionContext` through an explicit sketch-state adapter.
- New 3D features must not be added as metadata-only operations once feature-history implementation begins.
- The synchronous `extrude_profile` path remains accepted legacy technical debt, but v1 feature history is a separate pure rebuild path and never replays that external side effect.
- The v1 document envelope, revision checks, legacy wrapping, deterministic extrusion rebuild, persistence, and feature undo/redo are implemented. Multi-sketch authoring, kernel materialization, and default-on migration are not claimed.

## Boundary ownership

- Schema/version owner: `sketchmath.models`.
- Persistence/revision owner: `backend/sketchmath`.
- Solver/topology consumers: immutable sketch snapshots and stable entity IDs.
- Kernel consumer: validated feature/rebuild requests only.
