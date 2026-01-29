from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir() -> str:
    return os.getenv("FRIDAY_DATA_DIR", "/data")


def log_event(
    event_type: str,
    payload: Dict[str, Any],
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> None:
    entry = {
        "ts": _utc_ts(),
        "event": event_type,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "payload": payload,
    }
    base = Path(_data_dir()) / "audit"
    base.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"
    path = base / filename
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
