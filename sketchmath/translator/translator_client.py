from __future__ import annotations

from pathlib import Path


_PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    path = _PROMPTS_ROOT / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"SketchMath prompt not found: {name}")
    return path.read_text(encoding="utf-8")
