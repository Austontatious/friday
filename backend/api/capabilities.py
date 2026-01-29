from __future__ import annotations

from fastapi import APIRouter

from backend.core.capabilities import get_capabilities

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def capabilities():
    return get_capabilities()
