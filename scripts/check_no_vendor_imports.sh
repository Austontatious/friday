#!/usr/bin/env bash
set -euo pipefail

# Fail if runtime code imports from vendor/moltbot_ref.
# Allow docs/, vendor/, and this guard script itself.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATTERN='vendor\.moltbot_ref|moltbot_ref'

if command -v rg >/dev/null 2>&1; then
  BAD=$(rg -n --hidden --glob '!vendor/**' --glob '!docs/**' --glob '!scripts/check_no_vendor_imports.sh' "$PATTERN" "$ROOT" || true)
else
  BAD=$(grep -RIn --exclude-dir vendor --exclude-dir docs --exclude check_no_vendor_imports.sh -E "$PATTERN" "$ROOT" || true)
fi

if [[ -n "$BAD" ]]; then
  echo "ERROR: Found forbidden imports/references to vendor/moltbot_ref:"
  echo "$BAD"
  exit 1
fi

echo "OK: No vendor/moltbot_ref imports found."
