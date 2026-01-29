#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def load_cases(path: Path) -> List[Dict[str, str]]:
    cases: List[Dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("Each line must be a JSON object")
        cases.append(data)
    return cases


def validate_cases(cases: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    if limit > 0:
        cases = cases[:limit]
    seen = set()
    for case in cases:
        cid = case.get("id")
        prompt = case.get("prompt")
        expected = case.get("expected")
        if not cid or not prompt or not expected:
            raise ValueError(f"Invalid case: {case}")
        if cid in seen:
            raise ValueError(f"Duplicate id: {cid}")
        seen.add(cid)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate regression suite JSONL")
    parser.add_argument("--file", default="tools/eval/regression_suite.jsonl")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"Missing regression suite: {path}")

    cases = load_cases(path)
    checked = validate_cases(cases, args.limit)
    print(f"[regression] cases ok: {len(checked)} of {len(cases)}")


if __name__ == "__main__":
    main()
