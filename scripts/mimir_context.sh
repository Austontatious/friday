#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/mimir_context.sh status
  scripts/mimir_context.sh index
  scripts/mimir_context.sh query "<task text>"
  scripts/mimir_context.sh bundle "<task text>"

Environment overrides:
  MIMIR_REPO   Path to Mimir repo (default: /mnt/data/Mimir)
  TARGET_REPO  Path to target repo (default: parent of this script)
  PYTHON       Python executable (default: python3)
EOF
}

COMMAND="${1:-}"
TASK_TEXT="${2:-}"
MIMIR_REPO="${MIMIR_REPO:-/mnt/data/Mimir}"
PYTHON_BIN="${PYTHON:-python3}"
TARGET_REPO="${TARGET_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [[ -z "${COMMAND}" ]]; then
  usage
  exit 2
fi

if [[ ! -d "${MIMIR_REPO}/src/mimir" ]]; then
  echo "Mimir source not found at ${MIMIR_REPO}/src/mimir"
  echo "Set MIMIR_REPO to a valid Mimir checkout."
  exit 2
fi

run_mimir() {
  (cd "${MIMIR_REPO}" && PYTHONPATH=src "${PYTHON_BIN}" -m mimir.cli "$@")
}

case "${COMMAND}" in
  status)
    run_mimir info --repo "${TARGET_REPO}"
    run_mimir status --repo "${TARGET_REPO}"
    ;;
  index)
    run_mimir index --repo "${TARGET_REPO}"
    ;;
  query)
    if [[ -z "${TASK_TEXT}" ]]; then
      usage
      exit 2
    fi
    run_mimir query --repo "${TARGET_REPO}" --json "${TASK_TEXT}"
    ;;
  bundle)
    if [[ -z "${TASK_TEXT}" ]]; then
      usage
      exit 2
    fi
    run_mimir bundle --repo "${TARGET_REPO}" --json "${TASK_TEXT}"
    ;;
  *)
    usage
    exit 2
    ;;
esac
