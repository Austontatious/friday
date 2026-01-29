"""Auto‑register built‑in Friday tools."""
from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path

from .registry import register_tool

logger = logging.getLogger("friday.tools.init")

# --- Import concrete tool modules so their factories run ---
_builtin_modules = [
    "friday.tools.web_tools",
    "friday.tools.net_tools",
    "friday.tools.code_tools",
]

for mod_name in _builtin_modules:
    try:
        import_module(mod_name)
        logger.debug("Loaded tool module %s", mod_name)
    except Exception as exc:
        logger.error("Failed to import %s: %s", mod_name, exc)

# Example explicit registration for backwards compatibility
#from .web_tools import search_google
#register_tool(
#    name="web_search",
#    description="Search Google and return the top 3 results titles.",
#    usage_hint="Use for real‑time fact look‑ups.",
#    entrypoint=search_google,
#)
