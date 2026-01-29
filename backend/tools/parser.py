from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple


_CALL_KEYS = {"id", "name", "args"}


def _validate_call(obj: Any) -> Tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "tool_call_not_object"
    if not _CALL_KEYS.issubset(obj.keys()):
        return False, "tool_call_missing_keys"
    if not isinstance(obj.get("id"), str):
        return False, "tool_call_id_invalid"
    if not isinstance(obj.get("name"), str):
        return False, "tool_call_name_invalid"
    if not isinstance(obj.get("args"), dict):
        return False, "tool_call_args_invalid"
    return True, ""


def _extract_code_blocks(text: str) -> List[str]:
    blocks = []
    pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(text):
        blocks.append(match.group(1).strip())
    return blocks


def parse_tool_calls(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    calls: List[Dict[str, Any]] = []
    errors: List[str] = []

    for candidate in [text] + _extract_code_blocks(text):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            ok, err = _validate_call(item)
            if ok:
                calls.append({"id": item["id"], "name": item["name"], "args": item["args"]})
            else:
                errors.append(err)
        if calls:
            break

    if not calls and not errors:
        # parsed nothing; no error if no JSON present
        return [], []
    return calls, errors
