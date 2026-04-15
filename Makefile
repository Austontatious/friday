PYTHON ?= python3

.PHONY: run test eval lint enterprise-check enterprise-contracts enterprise-secrets enterprise-deps enterprise-vuln known-good mimir-status mimir-index mimir-query mimir-bundle

run:
	$(PYTHON) backend/main.py

test:
	$(PYTHON) -m pytest -q tests/test_codex_standards.py --noconftest

eval:
	$(PYTHON) evals/runner.py --check

lint:
	$(PYTHON) -m py_compile core/config.py core/prompt_loader.py core/llm.py core/trace.py tests/test_codex_standards.py evals/runner.py

enterprise-contracts:
	@if [ -d /mnt/data/Bifrost/src ]; then \
		PYTHONPATH=/mnt/data/Bifrost/src $(PYTHON) -m bifrost.boundary_drift --repo friday; \
	else \
		echo "enterprise-contracts: Bifrost boundary drift checker unavailable, skipping cross-project boundary check"; \
	fi

enterprise-secrets:
	@set -e; \
	PAT='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{36}|AIza[0-9A-Za-z\\-_]{35})'; \
	OUT=$$(git ls-files -z | xargs -0 -r rg -n "$$PAT" 2>/dev/null || true); \
	if [ -n "$$OUT" ]; then \
		echo "$$OUT"; \
		echo "enterprise-secrets: potential secret material detected"; \
		exit 1; \
	fi; \
	echo "enterprise-secrets: no high-confidence secret patterns found"

enterprise-deps:
	@mkdir -p artifacts/dependency
	@$(PYTHON) -m pip list --format=json > artifacts/dependency/pip-list.json || true
	@if [ -f package.json ]; then npm ls --json --all > artifacts/dependency/npm-tree.json || true; fi
	@echo "enterprise-deps: wrote dependency inventory under artifacts/dependency"

enterprise-vuln:
	@if command -v pip-audit >/dev/null 2>&1; then \
		pip-audit || true; \
	else \
		echo "enterprise-vuln: pip-audit not installed; skipped"; \
	fi
	@if command -v npm >/dev/null 2>&1 && [ -f package.json ]; then \
		npm audit --audit-level=high || true; \
	else \
		echo "enterprise-vuln: npm audit skipped (npm or package.json unavailable)"; \
	fi

enterprise-check: lint test eval enterprise-contracts enterprise-secrets
	@echo "enterprise-check: completed"

known-good: enterprise-check
	@mkdir -p artifacts/known_good
	@ts=$$(date -u +%Y%m%dT%H%M%SZ); \
	commit=$$(git rev-parse --short HEAD 2>/dev/null || echo no-commit); \
	out="artifacts/known_good/$$ts.json"; \
	printf '{\n  "timestamp_utc": "%s",\n  "commit": "%s",\n  "validation": "make enterprise-check"\n}\n' "$$ts" "$$commit" > "$$out"; \
	echo "known-good artifact: $$out"

mimir-status:
	@bash scripts/mimir_context.sh status

mimir-index:
	@bash scripts/mimir_context.sh index

mimir-query:
	@if [ -z "$(TASK)" ]; then \
		echo "Usage: make mimir-query TASK='task description'"; \
		exit 2; \
	fi
	@bash scripts/mimir_context.sh query "$(TASK)"

mimir-bundle:
	@if [ -z "$(TASK)" ]; then \
		echo "Usage: make mimir-bundle TASK='task description'"; \
		exit 2; \
	fi
	@bash scripts/mimir_context.sh bundle "$(TASK)"
