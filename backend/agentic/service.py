from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional

from backend.agentic.events import (
    clear_agent_run_context,
    emit_agent_event,
    register_agent_run_context,
)
from backend.agentic.queue import run_in_agent_queue, reset_agent_queue_for_tests
from backend.agentic.wait import (
    get_run_snapshot,
    record_run_finished,
    record_run_started,
    reset_run_wait_state_for_tests,
    wait_for_run,
)
from backend.core.chat_engine import ChatError, run_chat
from backend.security.trust import TrustContext

logger = logging.getLogger("friday.agentic.service")


def _now_ms() -> int:
    return int(time.time() * 1000)


class AgentRunService:
    def __init__(self) -> None:
        self._state_lock = threading.Lock()
        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._idempotency_index: Dict[str, str] = {}

    async def submit_run(
        self,
        *,
        payload: Dict[str, Any],
        trust: TrustContext,
        require_confirm: Optional[bool],
        session_key: str,
        lane: str = "main",
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_run_id = str(run_id or idempotency_key or uuid.uuid4().hex).strip()
        if not resolved_run_id:
            resolved_run_id = uuid.uuid4().hex
        accepted_at = _now_ms()
        idempotency = str(idempotency_key or "").strip() or None

        with self._state_lock:
            if idempotency and idempotency in self._idempotency_index:
                existing_run_id = self._idempotency_index[idempotency]
                return {
                    "run_id": existing_run_id,
                    "status": "accepted",
                    "accepted_at": accepted_at,
                    "cached": True,
                }
            existing_task = self._tasks.get(resolved_run_id)
            if existing_task is not None and not existing_task.done():
                return {
                    "run_id": resolved_run_id,
                    "status": "accepted",
                    "accepted_at": accepted_at,
                    "cached": True,
                }

            task = asyncio.create_task(
                self._execute_run(
                    run_id=resolved_run_id,
                    payload=dict(payload),
                    trust=trust,
                    require_confirm=require_confirm,
                    session_key=session_key,
                    lane=lane,
                )
            )
            self._tasks[resolved_run_id] = task
            if idempotency:
                self._idempotency_index[idempotency] = resolved_run_id

        return {
            "run_id": resolved_run_id,
            "status": "accepted",
            "accepted_at": accepted_at,
        }

    async def _execute_run(
        self,
        *,
        run_id: str,
        payload: Dict[str, Any],
        trust: TrustContext,
        require_confirm: Optional[bool],
        session_key: str,
        lane: str,
    ) -> None:
        started_at = _now_ms()
        register_agent_run_context(run_id, session_key=session_key)
        record_run_started(run_id, started_at=started_at)
        emit_agent_event(
            run_id=run_id,
            stream="lifecycle",
            data={"phase": "start", "started_at": started_at},
            session_key=session_key,
        )

        try:
            async def _run_once() -> Dict[str, Any]:
                return await run_chat(payload, trust=trust, require_confirm=require_confirm)

            response = await run_in_agent_queue(
                session_key=session_key,
                lane=lane,
                fn=_run_once,
            )
            with self._state_lock:
                self._results[run_id] = {"status": "ok", "result": response}

            for index, tool_event in enumerate(response.get("tools") or []):
                if isinstance(tool_event, dict):
                    emit_agent_event(
                        run_id=run_id,
                        stream="tool",
                        data={"index": index, **tool_event},
                        session_key=session_key,
                    )

            assistant_text = str(response.get("assistant_text") or response.get("text") or "").strip()
            if assistant_text:
                emit_agent_event(
                    run_id=run_id,
                    stream="assistant",
                    data={"text": assistant_text},
                    session_key=session_key,
                )

            meta = response.get("meta") if isinstance(response, dict) else {}
            runtime_events = meta.get("runtime_events") if isinstance(meta, dict) else []
            for event in runtime_events or []:
                if isinstance(event, dict):
                    emit_agent_event(
                        run_id=run_id,
                        stream="runtime",
                        data=event,
                        session_key=session_key,
                    )

            ended_at = _now_ms()
            emit_agent_event(
                run_id=run_id,
                stream="lifecycle",
                data={"phase": "end", "started_at": started_at, "ended_at": ended_at, "aborted": False},
                session_key=session_key,
            )
            record_run_finished(
                run_id,
                status="ok",
                started_at=started_at,
                ended_at=ended_at,
            )
        except ChatError as exc:
            ended_at = _now_ms()
            error_payload = {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "retryable": exc.retryable,
                "status_code": exc.status_code,
            }
            with self._state_lock:
                self._results[run_id] = {"status": "error", "error": error_payload}
            emit_agent_event(
                run_id=run_id,
                stream="error",
                data=error_payload,
                session_key=session_key,
            )
            emit_agent_event(
                run_id=run_id,
                stream="lifecycle",
                data={
                    "phase": "error",
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "error": f"{exc.code}:{exc.message}",
                },
                session_key=session_key,
            )
            record_run_finished(
                run_id,
                status="error",
                started_at=started_at,
                ended_at=ended_at,
                error=f"{exc.code}:{exc.message}",
            )
        except Exception as exc:
            ended_at = _now_ms()
            logger.exception("agent_run_failed run_id=%s error=%s", run_id, exc)
            with self._state_lock:
                self._results[run_id] = {"status": "error", "error": {"message": str(exc)}}
            emit_agent_event(
                run_id=run_id,
                stream="error",
                data={"message": str(exc)},
                session_key=session_key,
            )
            emit_agent_event(
                run_id=run_id,
                stream="lifecycle",
                data={"phase": "error", "started_at": started_at, "ended_at": ended_at, "error": str(exc)},
                session_key=session_key,
            )
            record_run_finished(
                run_id,
                status="error",
                started_at=started_at,
                ended_at=ended_at,
                error=str(exc),
            )
        finally:
            with self._state_lock:
                task = self._tasks.get(run_id)
                if task is asyncio.current_task():
                    self._tasks.pop(run_id, None)
            clear_agent_run_context(run_id)

    async def wait_for_run(
        self,
        run_id: str,
        *,
        timeout_ms: int = 30_000,
        include_result: bool = False,
    ) -> Optional[Dict[str, Any]]:
        snapshot = await wait_for_run(run_id, timeout_ms)
        if snapshot is None:
            return None

        payload: Dict[str, Any] = {
            "run_id": snapshot.run_id,
            "status": snapshot.status,
            "started_at": snapshot.started_at,
            "ended_at": snapshot.ended_at,
        }
        if snapshot.error:
            payload["error"] = snapshot.error

        if include_result:
            with self._state_lock:
                result_entry = self._results.get(run_id)
            if result_entry:
                if result_entry.get("status") == "ok":
                    payload["result"] = result_entry.get("result")
                elif result_entry.get("status") == "error":
                    payload["result_error"] = result_entry.get("error")
        return payload

    async def get_run_status(self, run_id: str, *, include_result: bool = False) -> Optional[Dict[str, Any]]:
        snapshot = get_run_snapshot(run_id)
        if snapshot is None:
            return None

        payload: Dict[str, Any] = {
            "run_id": snapshot.run_id,
            "status": snapshot.status,
            "started_at": snapshot.started_at,
            "ended_at": snapshot.ended_at,
        }
        if snapshot.error:
            payload["error"] = snapshot.error

        if include_result:
            with self._state_lock:
                result_entry = self._results.get(run_id)
            if result_entry:
                if result_entry.get("status") == "ok":
                    payload["result"] = result_entry.get("result")
                elif result_entry.get("status") == "error":
                    payload["result_error"] = result_entry.get("error")
        return payload

    def reset_for_tests(self) -> None:
        with self._state_lock:
            self._tasks.clear()
            self._results.clear()
            self._idempotency_index.clear()
        reset_run_wait_state_for_tests()
        reset_agent_queue_for_tests()


agent_run_service = AgentRunService()
