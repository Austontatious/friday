from __future__ import annotations

import re
from typing import Any, Mapping


def resolve_workspace_id(payload: Mapping[str, Any], headers: Mapping[str, str]) -> str:
    raw = headers.get("X-Friday-Workspace") or str(payload.get("workspace_id") or "")
    raw = raw.strip() if raw else "default"
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw) or "default"
    return safe
