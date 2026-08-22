#!/usr/bin/env python3
"""Fail CI when tracked source files contain obvious live API credentials."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "OpenAI-style API key": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained PAT": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".7z", ".bin", ".gguf", ".pt", ".safetensors"}


def tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(p.decode()) for p in out.split(b"\0") if p]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path}:{line}: possible {label}")
    if findings:
        print("Potential committed secrets detected:")
        print("\n".join(findings))
        return 1
    print("No obvious API credentials found in tracked text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
