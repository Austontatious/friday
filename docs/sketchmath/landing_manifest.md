# SketchMath Gate A Landing Manifest

Updated: 2026-08-08

## Purpose

Publish the validated SketchMath product without also publishing unrelated work accumulated on local `phase0-stabilize`.

## Refs

- Remote base: `origin/phase0-stabilize` at `4ed99b3`.
- Complete local safety/source branch: `phase0-stabilize`.
- Deliberate branch: `sketchmath-product-gate-a`.
- Validated reconstructed code baseline: `54ff17e`.
- First published landing commit: `1a4c853` (`refs/heads/sketchmath-product-gate-a`, verified after push).
- Delta: 39 commits over the remote base, versus 72 commits on the mixed source branch after Gate A documentation.

## Selection Rule

The branch contains the SketchMath domain, API, UI, CAD adapter, tests, semantic evals, product documentation, and the smallest required deployment/validation infrastructure. It excludes unrelated memory, model-serving, conversational, Android, gateway, and adjacent-product work.

The directly selected source series is:

- SketchMath product commits from `645400d` through `8236828`, excluding the memory-only `cd5a377` patch that became empty after preserving the remote baseline memory.
- Gate A commits `406cf01`, `e357112`, `e47ff78`, `799a7db`, and `e792be9`.
- Required infrastructure commits `f6b76e3`, `706e7b6`, `70100ae`, `055f36c`, `6394cd8`, `5ff4d59`, `44f8c97`, `febcac9`, and `4f6df7b`.
- Landing-only validation scaffold `54ff17e`, extracting the required standards files from source commit `6cb3430` without its unrelated analytics-gateway feature.

Cherry-picking changes commit identities; the original source hashes above remain the provenance anchors. The reconstructed history is linear from the published base and requires no force push.

## Conflict Decisions

- Historical `PROJECT_MEMORY.md` additions from unrelated source history were excluded. One current Gate A record was retained.
- `Pillow>=10.0.0` was retained because SketchMath preview code imports it and a runtime dependency test enforces it.
- `PyMuPDF` was excluded because it arrived through unrelated source ancestry and no selected SketchMath runtime imports it.
- Untracked local runtime and analysis artifacts were neither staged nor modified.

## Validation at `54ff17e`

- 99 focused Python tests passed.
- 42 deterministic semantic eval cases passed.
- Generated schemas match the canonical Pydantic models.
- 37 focused frontend tests passed.
- TypeScript compilation passed.
- Production frontend build passed without a SketchMath source warning.
- 9 live Playwright workflows passed against the real backend, including STEP generation/download.
- Docker Compose configuration passed.
- 13 repository standards tests passed.
- `git diff --check origin/phase0-stabilize..54ff17e` passed.

The production build emits only the repository-wide stale Browserslist data notice, which is outside this product-only landing.

## Publication

The dedicated branch was created on the remote at `1a4c853` on 2026-08-08. `origin/phase0-stabilize` remained at `4ed99b3`; no force push, rebase, tag, release, or pull request was performed.

## Rollback

Delete or stop consuming the dedicated remote branch. The existing `origin/phase0-stabilize` ref is not rewritten, and the complete local source branch remains available for forensic comparison.
