"""Deprecated entrypoint. Use backend/main.py."""
from backend.main import app, run

__all__ = ["app", "run"]

if __name__ == "__main__":
    run()
