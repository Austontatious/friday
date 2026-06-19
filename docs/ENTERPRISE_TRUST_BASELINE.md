# Enterprise Trust Baseline

## Canonical Validation

Primary gate:
- `make enterprise-check`

Includes:
- standards gate (`tests/test_codex_standards.py`)
- eval gate (`evals/runner.py --check`)
- cross-project boundary drift check for Friday ownership surface
- high-confidence secret pattern scan

## Dependency and Security Visibility

- Dependency inventory: `make enterprise-deps`
- Vulnerability scan path: `make enterprise-vuln`

## Known-Good Checkpoint

- Generate known-good evidence artifact:
  - `make known-good`
- Artifact location:
  - `artifacts/known_good/<UTC timestamp>.json`

## Rollback Discipline

Default non-destructive rollback for shared branches:
- `git revert <commit_sha>`

Local recovery options:
- branch or tag checkout for investigation
- restore forward with a new validating commit
