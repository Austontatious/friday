from __future__ import annotations

import asyncio
from dataclasses import dataclass
import threading
import time
from typing import Dict, Optional

RUN_CACHE_TTL_MS = 10 * 60 * 1000
TERMINAL_STATUSES = {"ok", "error", "timeout"}


@dataclass(frozen=True)
class AgentRunSnapshot:
    run_id: str
    status: str
    started_at: Optional[int]
    ended_at: Optional[int]
    error: Optional[str]
    ts: int


_snapshots: Dict[str, AgentRunSnapshot] = {}
_lock = threading.Lock()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _prune_locked(now_ms: int) -> None:
    stale_ids = [run_id for run_id, snap in _snapshots.items() if now_ms - snap.ts > RUN_CACHE_TTL_MS]
    for run_id in stale_ids:
        _snapshots.pop(run_id, None)


def record_run_started(run_id: str, *, started_at: Optional[int] = None) -> None:
    now_ms = _now_ms()
    with _lock:
        _prune_locked(now_ms)
        existing = _snapshots.get(run_id)
        _snapshots[run_id] = AgentRunSnapshot(
            run_id=run_id,
            status="running",
            started_at=started_at or (existing.started_at if existing else now_ms),
            ended_at=None,
            error=None,
            ts=now_ms,
        )


def record_run_finished(
    run_id: str,
    *,
    status: str,
    started_at: Optional[int] = None,
    ended_at: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    now_ms = _now_ms()
    with _lock:
        _prune_locked(now_ms)
        existing = _snapshots.get(run_id)
        _snapshots[run_id] = AgentRunSnapshot(
            run_id=run_id,
            status=status,
            started_at=started_at or (existing.started_at if existing else now_ms),
            ended_at=ended_at or now_ms,
            error=error,
            ts=now_ms,
        )


def get_run_snapshot(run_id: str) -> Optional[AgentRunSnapshot]:
    now_ms = _now_ms()
    with _lock:
        _prune_locked(now_ms)
        return _snapshots.get(run_id)


async def wait_for_run(run_id: str, timeout_ms: int) -> Optional[AgentRunSnapshot]:
    timeout_ms = max(int(timeout_ms), 0)
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while True:
        snapshot = get_run_snapshot(run_id)
        if snapshot and snapshot.status in TERMINAL_STATUSES:
            return snapshot
        if time.monotonic() >= deadline:
            return None
        await asyncio.sleep(0.05)


def reset_run_wait_state_for_tests() -> None:
    with _lock:
        _snapshots.clear()
