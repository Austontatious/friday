from __future__ import annotations

from fastapi import APIRouter

from backend.core.llm import llm_client

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/readyz")
def readyz():
    llm_ready = llm_client.ready()
    return {
        "ok": bool(llm_ready),
        "llm": llm_ready,
        "memory": True,
    }
