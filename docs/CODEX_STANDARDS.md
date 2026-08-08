# CODEX Standards

## Baseline Reference
- `/home/unix/codex-standards/BASELINE.md`

## Required Directories
- `prompts/`
- `prompts/system/`
- `prompts/tasks/`
- `prompts/evals/`
- `evals/`
- `evals/datasets/`
- `evals/cases/`
- `core/`
- `tests/`
- `docs/`

## Required Files
- `Makefile`
- `core/config.py`
- `core/prompt_loader.py`
- `core/llm.py`
- `core/trace.py`
- `evals/runner.py`
- `tests/test_codex_standards.py`

## Make Targets
- `run`
- `test`
- `eval`
- `lint`

## Prompt Scan Roots
- `backend/core/prompt_builder.py`
- `agents/`
- `huginn/`
- `tools/eval/verify_lexi_vllm.py`

## Config Scan Roots
- `core/`
- `backend/core/llm.py`
- `backend/core/prompt_builder.py`
- `backend/telemetry/mimir_trace.py`

## Model Interface Scan Roots
- `core/`
- `backend/core/`
- `tools/eval/`

## Canonical Prompt Surfaces
- `prompts/`

## Canonical Config Surfaces
- `core/config.py`
- `.env.example`
- `.env.models.example`
- `backend/core/capabilities.py`
- `backend/memory/factory.py`
- `backend/telemetry/mimir_trace.py`

## Canonical Model Interface Surfaces
- `core/llm.py`
- `backend/core/llm.py`

## Temporary Prompt Exceptions
- `backend/core/prompt_builder.py`
- `agents/refactor.py`
- `huginn/core.py`
- `tools/eval/verify_lexi_vllm.py`

## Temporary Config Exceptions
- `backend/core/llm.py`
- `backend/core/prompt_builder.py`

## Temporary Model Interface Exceptions
- `None.`

## Core Rules
- No inline prompts in runtime code.
- No direct model SDK usage outside canonical interface surfaces.
- New env access belongs in typed config surfaces or in an explicit temporary exception.
- Friday prompt assembly must load from prompt files and Friday LLM tracing must remain callable even when noop.

## Contract Change Rules
- Request or response schema changes require a version bump.
- Prompt structure or retrieval format changes require compatibility review and test updates.

## Anti-Bloat Rule
- Do not add speculative frameworks, agent layers, or wrappers without runtime proof.

## Simplicity Rule
- Prefer prompt files, typed config, and explicit transport wrappers over hidden orchestration.

## Senior Architecture Guardrails
This repo follows the Senior Architecture Guardrails defined in `/home/unix/codex-standards/BASELINE.md`.

Key enforced rules:
- ADR required for major subsystems, contracts, schemas, and workflow patterns (`docs/decisions/`).
- Every shared boundary must define ownership (producer, consumer, schema owner, version owner, compatibility owner).
- Shared interfaces are stable contracts; internal reach-through and implicit schema mutation are forbidden.
- Hidden side effects are forbidden; writes must be explicit and read paths must not mutate state.
- Setup/bootstrap/migration scripts must be idempotent and safe to re-run.
- Shared contracts must be versioned and include schema + golden examples + compatibility notes.
- Contract testing is required on producer and consumer sides where applicable.
- One canonical path per concern; alternate paths require explicit justification.
- Failure modes, trust boundaries, and out-of-scope deferrals must be explicit.

## Validation
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`
- `python3 evals/runner.py --check`
- `python3 -m py_compile core/config.py core/prompt_loader.py core/llm.py core/trace.py tests/test_codex_standards.py evals/runner.py`

## Enterprise Trust Gates
- Canonical gate: `make enterprise-check`
- Dependency inventory: `make enterprise-deps`
- Vulnerability scan path: `make enterprise-vuln`
- Known-good artifact: `make known-good` (writes `artifacts/known_good/<timestamp>.json`)
- Repo-specific checkpoint/rollback discipline: `docs/ENTERPRISE_TRUST_BASELINE.md`
