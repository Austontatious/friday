from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

TRUSTED_USER = "trusted_user"
UNTRUSTED_CHANNEL = "untrusted_channel"
UNTRUSTED_DOCUMENT = "untrusted_document"


@dataclass
class TrustContext:
    level: str
    reasons: List[str]

    @property
    def has_untrusted(self) -> bool:
        return self.level != TRUSTED_USER


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _safe_tools() -> List[str]:
    raw = os.getenv("FRIDAY_TRUST_SAFE_TOOLS", "list_facts,search_local_logs")
    return [item.strip() for item in raw.split(",") if item.strip()]


def classify_request(payload: Mapping[str, Any], headers: Mapping[str, str]) -> TrustContext:
    reasons: List[str] = []
    header_trust = headers.get("X-Friday-Trust", "").strip().lower()
    payload_trust = str(payload.get("trust") or "").strip().lower()
    source_type = str(payload.get("source_type") or "").strip().lower()

    if header_trust:
        if header_trust in {"trusted", "trusted_user"}:
            return TrustContext(TRUSTED_USER, ["header_trust"])
        if header_trust in {"channel", "untrusted_channel"}:
            return TrustContext(UNTRUSTED_CHANNEL, ["header_trust"])
        if header_trust in {"document", "untrusted_document"}:
            return TrustContext(UNTRUSTED_DOCUMENT, ["header_trust"])

    if payload_trust:
        if payload_trust in {"trusted", "trusted_user"}:
            return TrustContext(TRUSTED_USER, ["payload_trust"])
        if payload_trust in {"channel", "untrusted_channel"}:
            return TrustContext(UNTRUSTED_CHANNEL, ["payload_trust"])
        if payload_trust in {"document", "untrusted_document"}:
            return TrustContext(UNTRUSTED_DOCUMENT, ["payload_trust"])

    if source_type in {"channel", "slack", "discord", "email", "web"}:
        reasons.append("source_type")
        return TrustContext(UNTRUSTED_CHANNEL, reasons)

    if source_type in {"document", "ocr", "pdf", "webpage"}:
        reasons.append("source_type")
        return TrustContext(UNTRUSTED_DOCUMENT, reasons)

    if payload.get("untrusted_context"):
        reasons.append("untrusted_context")
        return TrustContext(UNTRUSTED_DOCUMENT, reasons)

    return TrustContext(TRUSTED_USER, ["default"])


def require_confirmation(trust: TrustContext) -> bool:
    mode = _env("FRIDAY_TRUST_MODE", "strict").lower()
    if mode == "dev":
        return False
    return trust.has_untrusted


def is_safe_tool(tool_name: str) -> bool:
    return tool_name in _safe_tools()
