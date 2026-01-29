#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import subprocess
from typing import Any, Dict

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = os.getenv("FRIDAY_BASE_URL", "http://localhost:9001")


def env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def log(msg: str) -> None:
    print(f"[smoke] {msg}")


def api_check() -> None:
    try:
        health = requests.get(f"{BASE_URL}/healthz", timeout=2)
        log(f"healthz: {health.status_code}")
    except Exception as exc:
        log(f"healthz skipped ({exc})")
        return

    ready = requests.get(f"{BASE_URL}/readyz", timeout=2).json()
    log(f"readyz ok={ready.get('ok')}")

    caps = requests.get(f"{BASE_URL}/api/capabilities", timeout=2).json()
    expected_llm = env_bool("FRIDAY_LLM_ENABLED", "0")
    if caps.get("enabled", {}).get("llm") != expected_llm:
        raise AssertionError("capabilities llm flag mismatch")

    chat = requests.post(f"{BASE_URL}/api/chat", json={"prompt": "Hello"}, timeout=5).json()
    if not expected_llm:
        if "LLM disabled" not in chat.get("text", ""):
            raise AssertionError("LLM disabled message missing")
    log("api checks ok")


def memory_check() -> None:
    os.environ["FRIDAY_MEMORY_PERSIST_ENABLED"] = "1"
    os.environ["FRIDAY_MEMORY_FACTS_ENABLED"] = "1"
    os.environ["FRIDAY_MEMORY_SUMMARIES_ENABLED"] = "1"
    os.environ["FRIDAY_MEMORY_CONSOLIDATION_ENABLED"] = "0"

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FRIDAY_DATA_DIR"] = tmp
        from backend.memory.service import MemoryService

        service = MemoryService()
        service.append_turn("user-1", "default", "user", "Remember that I like espresso.")
        service.remember_fact("user-1", "default", "drink", "espresso", tags=["preference"])
        bundle = service.retrieve("user-1", "default", "espresso", limit_turns=5)

        facts = bundle.get("relevant_facts", [])
        if not any(fact.get("value") == "espresso" for fact in facts):
            raise AssertionError("facts retrieval failed")

        log("memory checks ok")


def tool_check() -> None:
    from backend.tools import builtins as _builtins  # register tools
    from backend.security.trust import TrustContext
    from backend.tools.engine import execute_tool_call, validate_tool_call

    ok, error = validate_tool_call({"name": "remember_fact"})
    if ok or error.get("code") != "invalid_tool_call":
        raise AssertionError("tool schema validation failed")

    os.environ["FRIDAY_TOOLS_ENABLED"] = "1"
    os.environ["FRIDAY_TOOLS_REQUIRE_CONFIRM"] = "1"
    os.environ["FRIDAY_MEMORY_FACTS_ENABLED"] = "1"

    call = {"id": "t1", "name": "remember_fact", "args": {"key": "pref", "value": "short replies"}}
    trust = TrustContext(level="trusted_user", reasons=["smoke"])
    blocked = execute_tool_call(call, context_user_id="user-1", workspace_id="default", require_confirm=True, approved=False, trust=trust)
    if blocked.get("ok") is True or blocked.get("error", {}).get("code") != "requires_confirmation":
        raise AssertionError("tool should require confirmation")

    allowed = execute_tool_call(call, context_user_id="user-1", workspace_id="default", require_confirm=True, approved=True, trust=trust)
    if not allowed.get("ok"):
        raise AssertionError("tool should execute after confirmation")

    log("tool checks ok")


def guard_vendor_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "check_no_vendor_imports.sh"
    if not script.exists():
        return
    try:
        subprocess.run([str(script)], check=True)
    except Exception as exc:
        raise AssertionError(f"vendor import guard failed: {exc}")


def main() -> None:
    try:
        api_check()
    except Exception as exc:
        log(f"api checks failed: {exc}")
    memory_check()
    tool_check()
    guard_vendor_imports()
    log("smoke eval complete")


if __name__ == "__main__":
    main()
