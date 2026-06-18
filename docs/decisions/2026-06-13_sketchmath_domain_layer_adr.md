# ADR: SketchMath Domain Layer Under the FRIDAY Gateway

## Problem
FRIDAY already owns alias/profile routing, prompt loading, JSON repair, trace sinks, and OpenAI-compatible model calls, but it does not yet provide a domain-specific geometry execution layer for human-directed point/line math and previewable CAD-style operations.

## Options Considered
1. Put geometry execution directly in the gateway router.
2. Add a separate SketchMath domain package below the gateway.
3. Build the geometry subsystem in a new service.

## Decision
Add a separate `sketchmath/` domain package below the existing FRIDAY gateway/control plane.

## Rationale
- Keeps routing and geometry execution isolated.
- Allows FRIDAY to continue owning alias/profile behavior.
- Lets SketchMath evolve its own typed command, preview, commit, and history contracts.

## Consequences
- New code paths must be tested independently.
- The gateway remains the translator/control plane, not the executor.
- Future FreeCAD/OpenCascade integration will land in SketchMath rather than in the gateway router.

## Explicit Deferrals
- No FreeCAD/OpenCascade adapter in this slice.
- No gateway router changes in this slice.
- No 3D CAD operations yet.
