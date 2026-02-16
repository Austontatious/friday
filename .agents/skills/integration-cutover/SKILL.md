# Skill: integration-cutover

## Objective
Cut over a legacy subsystem to a new provider behind an interface, with rollback safety.

## Steps
1. Discover live request path and data flow before editing.
2. Add provider interface + factory with env selection.
3. Keep legacy provider available for rollback.
4. Add runtime fallback when new provider is unavailable.
5. Wire pre-request enrichment and post-response writeback.
6. Keep user-visible behavior minimal and backward-compatible.
7. Add logs, flags, docs, and smoke checks.

## Rules
- Never vendor external service source into FRIDAY.
- Gate behavior with env flags.
- Do not block user replies on provider-side failures.
