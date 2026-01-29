"""Deprecated chat route. Use backend/api/chat.py."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/deprecated")
def deprecated():
    return {"status": "deprecated", "use": "/api/chat"}
