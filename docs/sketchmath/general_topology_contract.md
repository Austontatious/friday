# SketchMath General Planar Topology Contract

Validated implementation checkpoint: `b29d504` (`feat(sketchmath): add deterministic planar topology`)

Concurrent session-mutation hardening: `326e813` (`fix(sketchmath): serialize session mutations`)

## Authority

The backend topology result is the sole authority for bounded regions. React renders and selects the returned regions; it does not reconstruct topology independently.

Contract version `0.9` adds:

- `detect_regions`: preview-only region extraction.
- `select_region`: preview-only point-in-region selection.
- `make_region_profile`: atomic promotion of one current region into an outer `profile_2d` plus zero or more hole profiles.

Preview commands never mutate session state or history. Promotion re-detects current topology before commit, so a stale region ID is refused rather than rebound silently.

## Supported Geometry

Regular `line_2d`, `circle_2d`, and finite `arc_2d` entities participate. Point-backed line coordinates are resolved from their current source points. Construction lines, profiles, points, and unsupported entities do not become boundary curves.

Lines are exact within the node tolerance. Circles and finite arcs are converted to deterministic piecewise-linear boundaries with a maximum angular step of 2 degrees. The result reports this approximation policy.

## Determinism and Tolerances

- Node tolerance: `1e-7 mm`.
- Near-vertex warning threshold: `1e-5 mm`.
- Stable loop and region IDs are SHA-256-derived from canonicalized geometry and loop roles, not input ordering.
- Outer loops are counterclockwise; holes are clockwise.
- Region area is net planar area. A promoted outer profile stores its outer-loop area while its hole profiles remain explicit; `make_region_profile.value` and `metadata.net_area` report net area.
- Source curve IDs are retained on loops, regions, and promoted profiles for reference recovery.

No automatic near-vertex snap is performed. Geometry inside the near threshold but outside node tolerance remains separate and produces a diagnostic.

## Selection

Point selection returns one of:

- `selected`: exactly one region contains the point.
- `none`: no bounded region contains the point.
- `boundary`: the point lies on a region boundary within node tolerance.
- `ambiguous`: more than one returned region contains the point.
- `not_requested`: detection ran without a point.

Boundary clicks are not guessed. The browser asks the user to click clearly inside a region or choose a listed region.

## Diagnostics

The typed diagnostic envelope contains `code`, `severity`, `message`, implicated curve IDs, optional point, and structured detail. Current deterministic codes include:

- `degenerate_curve`
- `self_intersecting_curve`
- `near_vertex_gap`
- `overlapping_curves`
- `curve_intersection`
- `t_junction`
- `disconnected_components`
- `open_branches`
- `dangles`
- `invalid_rings`
- `no_bounded_regions`

Shared edges and overlaps are noded once for extraction and remain visible as diagnostics rather than being silently discarded.

## Promotion and References

`make_region_profile` creates the hole profiles and outer profile in one committed operation and one undo step. Every generated profile stores `source_region_id` and `source_curve_ids`.

Topology-backed profile transforms expand to the source boundary bundle. After a valid transform or source edit, the executor first matches the prior stable geometry and source set, then attempts an exact source-set recovery. Missing, ambiguous, or structurally changed hole references fail atomically with a structured topology-reference error.

Split, trim, and extend still reject already referenced target curves. General region extraction and reference recovery do not imply arbitrary automatic curve-repair semantics.

## Acceptance Evidence

- Adversarial unit coverage: disjoint loops, nested holes/islands, multiple holes, shared edges, branches, intersections, boundary/inside/outside selection, touching and overlapping loops, near gaps, self-intersection, nested circles, finite arcs, stable IDs, promotion, undo, transforms, and broken-reference rollback.
- API coverage: detect, select, promote, disk reload, and per-session concurrent-commit serialization.
- Semantic coverage: v0.9 detect/select/promote fixtures.
- Browser coverage: independent-line promotion and nested annular point selection with a T-junction diagnostic, promotion, hole persistence, stable source region, and reload.

The validated checkpoint matrix is 187 Python tests, 65 semantic cases, 66 frontend tests, and 17 serial shell/product Playwright workflows, plus schema drift, TypeScript, production build, Compose, and 13 standards checks.
