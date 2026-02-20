from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Awaitable, Callable, Dict, Tuple, TypeVar

logger = logging.getLogger("friday.agentic.queue")

T = TypeVar("T")

_session_locks: Dict[Tuple[int, str], asyncio.Lock] = {}
_global_lane_limits: Dict[Tuple[int, str], asyncio.Semaphore] = {}
_session_guard = asyncio.Lock()
_global_guard = asyncio.Lock()


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _lane_concurrency(lane: str) -> int:
    cleaned = lane.strip().lower()
    if cleaned == "main":
        return _env_int("FRIDAY_AGENT_MAIN_MAX_CONCURRENT", _env_int("FRIDAY_AGENT_MAX_CONCURRENT", 4))
    if cleaned == "subagent":
        return _env_int("FRIDAY_AGENT_SUBAGENT_MAX_CONCURRENT", _env_int("FRIDAY_AGENT_MAX_CONCURRENT", 8))
    return _env_int("FRIDAY_AGENT_MAX_CONCURRENT", 1)


def _loop_id() -> int:
    return id(asyncio.get_running_loop())


async def _get_session_lock(session_key: str) -> asyncio.Lock:
    key = (_loop_id(), session_key)
    async with _session_guard:
        lock = _session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[key] = lock
        return lock


async def _get_lane_semaphore(lane: str) -> asyncio.Semaphore:
    cleaned_lane = lane.strip() or "main"
    key = (_loop_id(), cleaned_lane)
    limit = _lane_concurrency(cleaned_lane)
    async with _global_guard:
        sem = _global_lane_limits.get(key)
        existing_limit = getattr(sem, "_friday_limit", None) if sem is not None else None
        if sem is None or existing_limit != limit:
            sem = asyncio.Semaphore(limit)
            setattr(sem, "_friday_limit", limit)
            _global_lane_limits[key] = sem
        return sem


async def run_in_agent_queue(
    *,
    session_key: str,
    lane: str,
    fn: Callable[[], Awaitable[T]],
) -> T:
    resolved_session = session_key.strip() or "session:anonymous"
    resolved_lane = lane.strip() or "main"

    session_lock = await _get_session_lock(resolved_session)
    session_wait_started = time.perf_counter()
    async with session_lock:
        session_wait_ms = int((time.perf_counter() - session_wait_started) * 1000)
        if session_wait_ms > 2000:
            logger.info(
                "agent_queue_wait session_key=%s lane=%s wait_ms=%s stage=session",
                resolved_session,
                resolved_lane,
                session_wait_ms,
            )

        lane_sem = await _get_lane_semaphore(resolved_lane)
        lane_wait_started = time.perf_counter()
        async with lane_sem:
            lane_wait_ms = int((time.perf_counter() - lane_wait_started) * 1000)
            if lane_wait_ms > 2000:
                logger.info(
                    "agent_queue_wait session_key=%s lane=%s wait_ms=%s stage=lane",
                    resolved_session,
                    resolved_lane,
                    lane_wait_ms,
                )
            return await fn()


def reset_agent_queue_for_tests() -> None:
    _session_locks.clear()
    _global_lane_limits.clear()
