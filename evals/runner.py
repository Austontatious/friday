from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"
DATASETS_DIR = ROOT / "datasets"


def run_check() -> int:
    errors: list[str] = []
    if not CASES_DIR.is_dir():
        errors.append("missing evals/cases")
    if not DATASETS_DIR.is_dir():
        errors.append("missing evals/datasets")
    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.is_dir() else []
    if not case_files:
        errors.append("missing deterministic eval case JSON files")
    for path in case_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON eval case {path.relative_to(ROOT.parent)}: {exc}")

    if errors:
        for error in errors:
            print(f"eval-check: {error}")
        return 1
    print(f"eval-check: ok cases={len(case_files)} datasets_dir={DATASETS_DIR.relative_to(ROOT.parent)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate eval scaffold and deterministic cases")
    args = parser.parse_args()
    if args.check:
        return run_check()
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
