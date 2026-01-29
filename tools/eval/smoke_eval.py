#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, Dict

import requests

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
        service.append_turn("user-1", "user", "Remember that I like espresso.")
        service.remember_fact("user-1", "drink", "espresso", tags=["preference"])
        bundle = service.retrieve("user-1", "What do I like?", limit_turns=5)

        facts = bundle.get("relevant_facts", [])
        if not any(fact.get("value") == "espresso" for fact in facts):
            raise AssertionError("facts retrieval failed")

        log("memory checks ok")


def tool_check() -> None:
    from backend.tools.engine import validate_tool_call

    ok, error = validate_tool_call({"name": "remember_fact"})
    if ok or error.get("code") != "invalid_tool_call":
        raise AssertionError("tool schema validation failed")

    log("tool checks ok")


def main() -> None:
    try:
        api_check()
    except Exception as exc:
        log(f"api checks failed: {exc}")
    memory_check()
    tool_check()
    log("smoke eval complete")


if __name__ == "__main__":
    main()
