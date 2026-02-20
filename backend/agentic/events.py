from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Dict, Optional, Set


@dataclass(frozen=True)
class AgentEvent:
    run_id: str
    seq: int
    stream: str
    ts: int
    data: Dict[str, Any]
    session_key: Optional[str] = None


_seq_by_run: Dict[str, int] = {}
_run_context: Dict[str, Dict[str, Any]] = {}
_listeners: Set[Callable[[AgentEvent], None]] = set()
_lock = threading.Lock()


def register_agent_run_context(run_id: str, *, session_key: Optional[str] = None) -> None:
    if not run_id:
        return
    with _lock:
        context = _run_context.setdefault(run_id, {})
        if session_key:
            context["session_key"] = str(session_key)


def clear_agent_run_context(run_id: str) -> None:
    if not run_id:
        return
    with _lock:
        _run_context.pop(run_id, None)


def emit_agent_event(
    *,
    run_id: str,
    stream: str,
    data: Optional[Dict[str, Any]] = None,
    session_key: Optional[str] = None,
) -> AgentEvent:
    payload = dict(data or {})
    with _lock:
        next_seq = _seq_by_run.get(run_id, 0) + 1
        _seq_by_run[run_id] = next_seq
        context_session = _run_context.get(run_id, {}).get("session_key")
        resolved_session = session_key or context_session
        event = AgentEvent(
            run_id=run_id,
            seq=next_seq,
            stream=stream,
            ts=int(time.time() * 1000),
            data=payload,
            session_key=resolved_session,
        )
        listeners = list(_listeners)

    for listener in listeners:
        try:
            listener(event)
        except Exception:
            # Event listeners must not break runtime behavior.
            continue
    return event


def on_agent_event(listener: Callable[[AgentEvent], None]) -> Callable[[], None]:
    with _lock:
        _listeners.add(listener)

    def unsubscribe() -> None:
        with _lock:
            _listeners.discard(listener)

    return unsubscribe


def reset_agent_events_for_tests() -> None:
    with _lock:
        _seq_by_run.clear()
        _run_context.clear()
        _listeners.clear()
