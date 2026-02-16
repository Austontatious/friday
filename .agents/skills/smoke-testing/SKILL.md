# Skill: smoke-testing

## Objective
Provide a fast end-to-end confidence check for local development.

## Required checks
1. Service health endpoint returns success.
2. Main user route returns a valid response payload.
3. New feature metadata appears when relevant.
4. Failure-mode check proves graceful fallback.

## Implementation notes
- Prefer bash + `curl` so checks run anywhere.
- Use deterministic payloads and explicit exit codes.
- Print concise pass/fail messages per step.
