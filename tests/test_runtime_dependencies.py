def test_unconditionally_imported_vision_dependency_is_declared() -> None:
    from pathlib import Path

    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8").lower()
    assert any(line.strip().startswith("pillow") for line in requirements.splitlines())
