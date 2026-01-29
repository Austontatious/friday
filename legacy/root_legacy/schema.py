"""Deprecated schema server. Use backend/main.py."""
from fastapi import FastAPI

app = FastAPI()

@app.get("/deprecated")
def deprecated():
    return {"status": "deprecated", "use": "/api/chat"}
