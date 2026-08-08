from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import SketchMathError
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext
from sketchmath.translator.translator_service import translate_utterance


REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = REPO_ROOT / "evals" / "cases"
RESULTS_PATH = REPO_ROOT / "evals" / "sketchmath_semantic_results.json"
VOLATILE_RESULT_KEYS = {"artifact_created_at"}


def _stable_result_value(value: Any) -> Any:
    """Remove runtime-only fields before writing the tracked eval report."""
    if isinstance(value, dict):
        stable = {
            key: _stable_result_value(item)
            for key, item in value.items()
            if key not in VOLATILE_RESULT_KEYS
        }
        if "command_id" in stable:
            stable["command_id"] = "<generated>"
        if stable.get("command_type") == "make_profile" and isinstance(stable.get("parameters"), dict):
            parameters = stable["parameters"]
            if isinstance(parameters.get("name"), str) and parameters["name"].startswith("profile_"):
                parameters["name"] = "<generated_profile>"
        return stable
    if isinstance(value, list):
        return [_stable_result_value(item) for item in value]
    return value


def _load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Eval case must be an object: {path}")
    return payload


def _eval_case_paths() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(CASES_ROOT.rglob("sketchmath_*.json")):
        payload = _load_case(path)
        if isinstance(payload.get("input"), dict) and (
            ("command" in payload["input"] and "selection_context" in payload["input"]) or ("utterance" in payload["input"] and "selection_context" in payload["input"])
        ):
            paths.append(path)
    return paths


def _extract_state_snapshot(state: SelectionContext) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for item in state.items:
        if hasattr(item, "coords"):
            snapshot[item.id] = list(item.coords)
        elif hasattr(item, "start") and hasattr(item, "end"):
            snapshot[item.id] = {"start": list(item.start), "end": list(item.end)}
        elif hasattr(item, "origin") and hasattr(item, "direction"):
            snapshot[item.id] = {"origin": list(item.origin), "direction": list(item.direction)}
        elif hasattr(item, "center") and hasattr(item, "radius"):
            snapshot[item.id] = {
                "center": list(item.center),
                "radius": item.radius,
                "center_point_id": getattr(item, "center_point_id", None),
            }
        elif hasattr(item, "vertices"):
            snapshot[item.id] = {
                "vertices": [list(vertex) for vertex in item.vertices],
                "area": getattr(item, "area", None),
                "winding": getattr(item, "winding", None),
                "warnings": list(getattr(item, "warnings", [])),
            }
    return snapshot


def _compare_expected(result: Any, expected: dict[str, Any]) -> tuple[bool, str]:
    if "status" in expected and result.status != expected["status"]:
        return False, f"expected status {expected['status']!r}, got {result.status!r}"
    if "value" in expected and result.value != expected["value"]:
        if result.value is None or abs(result.value - expected["value"]) > 1e-6:
            return False, f"expected value {expected['value']!r}, got {result.value!r}"
    if "unit" in expected and result.unit != expected["unit"]:
        return False, f"expected unit {expected['unit']!r}, got {result.unit!r}"
    if "metadata" in expected:
        ok, reason = _match_value(result.metadata, expected["metadata"])
        if not ok:
            return False, f"metadata mismatch: {reason}"
    if "changed_entity_ids" in expected and result.changed_entity_ids != expected["changed_entity_ids"]:
        return False, f"expected changed ids {expected['changed_entity_ids']!r}, got {result.changed_entity_ids!r}"
    if "after" in expected:
        actual_after = _extract_state_snapshot(result.after)
        for entity_id, expected_value in expected["after"].items():
            if entity_id not in actual_after:
                return False, f"missing entity {entity_id!r} in result.after"
            ok, reason = _match_value(actual_after[entity_id], expected_value)
            if not ok:
                return False, f"entity {entity_id!r} mismatch: {reason}"
    if "history_length" in expected and expected["history_length"] != result.metadata.get("history_length"):
        return False, f"expected history_length {expected['history_length']!r}, got {result.metadata.get('history_length')!r}"
    return True, "ok"


def _compare_translation(actual: Any, expected: dict[str, Any]) -> tuple[bool, str]:  # noqa: ANN401
    if "status" in expected and actual.status != expected["status"]:
        return False, f"expected status {expected['status']!r}, got {actual.status!r}"
    if actual.status == "command":
        if actual.command is None:
            return False, "expected a command payload"
        expected_command = expected.get("command", {})
        if "command_type" in expected_command and actual.command.command_type != expected_command["command_type"]:
            return False, f"expected command_type {expected_command['command_type']!r}, got {actual.command.command_type!r}"
        if "selection" in expected_command and actual.command.selection != expected_command["selection"]:
            return False, f"expected selection {expected_command['selection']!r}, got {actual.command.selection!r}"
        if "parameters" in expected_command:
            for key, value in expected_command["parameters"].items():
                if actual.command.parameters.get(key) != value:
                    return False, f"expected parameters[{key!r}]={value!r}, got {actual.command.parameters.get(key)!r}"
    if "reason_contains" in expected:
        reason = actual.reason or ""
        if expected["reason_contains"] not in reason:
            return False, f"expected reason containing {expected['reason_contains']!r}, got {reason!r}"
    if "options" in expected and actual.options != expected["options"]:
        return False, f"expected options {expected['options']!r}, got {actual.options!r}"
    return True, "ok"


def _match_value(actual: Any, expected: Any, *, tolerance: float = 1e-6) -> tuple[bool, str]:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if abs(float(actual) - float(expected)) <= tolerance:
            return True, "ok"
        return False, f"expected {expected!r}, got {actual!r}"
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False, f"expected list length {len(expected)}, got {len(actual)}"
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            ok, reason = _match_value(actual_item, expected_item, tolerance=tolerance)
            if not ok:
                return False, f"index {index}: {reason}"
        return True, "ok"
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, expected_item in expected.items():
            if key not in actual:
                return False, f"missing key {key!r}"
            ok, reason = _match_value(actual[key], expected_item, tolerance=tolerance)
            if not ok:
                return False, f"key {key!r}: {reason}"
        return True, "ok"
    if actual == expected:
        return True, "ok"
    return False, f"expected {expected!r}, got {actual!r}"


def _run_case(path: Path) -> dict[str, Any]:
    payload = _load_case(path)
    name = payload.get("name", path.stem)
    input_payload = payload["input"]
    expected = payload["expected"]
    if "command" in input_payload:
        session = GeometrySession(SelectionContext.model_validate(input_payload["selection_context"]))
        command = GeometryCommand.model_validate(input_payload["command"])

        try:
            result = session.execute(command)
        except SketchMathError as exc:
            actual_error = exc.to_dict()
            if "error" not in expected:
                return {
                    "name": name,
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "status": "fail",
                    "diagnostic": f"unexpected error {actual_error}",
                }
            expected_error = expected["error"]
            if actual_error.get("code") != expected_error.get("code"):
                return {
                    "name": name,
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "status": "fail",
                    "diagnostic": f"expected error code {expected_error.get('code')!r}, got {actual_error.get('code')!r}",
                }
            return {
                "name": name,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "status": "pass",
                "diagnostic": actual_error,
            }

        if "error" in expected:
            return {
                "name": name,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "status": "fail",
                "diagnostic": "expected an error but execution succeeded",
            }

        ok, diagnostic = _compare_expected(result, expected)
        return {
            "name": name,
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "status": "pass" if ok else "fail",
            "diagnostic": diagnostic,
            "result": {
                "status": result.status,
                "value": result.value,
                "unit": result.unit,
                "changed_entity_ids": result.changed_entity_ids,
                "metadata": _stable_result_value(result.metadata),
                "after": _extract_state_snapshot(result.after),
            },
        }

    translation = translate_utterance(input_payload["utterance"], SelectionContext.model_validate(input_payload["selection_context"]))
    ok, diagnostic = _compare_translation(translation, expected)
    return {
        "name": name,
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "status": "pass" if ok else "fail",
        "diagnostic": diagnostic,
        "result": {
            "status": translation.status,
            "command": _stable_result_value(translation.command.model_dump(mode="json")) if translation.command is not None else None,
            "reason": translation.reason,
            "options": translation.options,
        },
    }


def run() -> int:
    case_paths = _eval_case_paths()
    results = [_run_case(path) for path in case_paths]
    payload = {
        "status": "pass" if all(result["status"] == "pass" for result in results) else "fail",
        "case_count": len(case_paths),
        "passed": sum(1 for result in results if result["status"] == "pass"),
        "failed": sum(1 for result in results if result["status"] == "fail"),
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    for result in results:
        print(f"[{result['status']}] {result['name']}: {result['diagnostic']}")
    print(f"[ok] wrote {RESULTS_PATH.relative_to(REPO_ROOT)}")
    return 0 if payload["status"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SketchMath semantic geometry evals")
    parser.add_argument("--check", action="store_true", help="run semantic evals and exit non-zero on failures")
    args = parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
