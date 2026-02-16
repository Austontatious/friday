# Skill: env-config-hygiene

## Objective
Keep configuration explicit, portable, and safe by default.

## Checklist
1. Add defaults to `.env.example`.
2. Thread vars into `docker-compose.yaml` env mapping.
3. Avoid hard-coded absolute paths.
4. Validate enum-like vars with sane fallback.
5. Log selected provider + key config at startup.

## Rules
- New features require env flags.
- Defaults should preserve baseline text-only operation.
