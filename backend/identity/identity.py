from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

ACCOUNT_HEADER = "X-Friday-Account-User"
AUTH_USER_HEADER = "X-Authenticated-User"
SESSION_HEADER = "X-Friday-Session"
DEVICE_HEADER = "X-Friday-Device"
USER_HEADER = "X-Friday-User"
SESSION_COOKIE = "friday_session"
DEVICE_COOKIE = "friday_device"
LOCAL_FALLBACK_ENTITY = "ent_local_user"

_ID_SANITIZER = re.compile(r"[^a-zA-Z0-9._:@-]+")


@dataclass
class IdentityResolution:
    user_id: str
    source: str
    set_session_cookie: Optional[str] = None
    set_device_cookie: Optional[str] = None


def _clean_identifier(value: str, *, limit: int = 96) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _ID_SANITIZER.sub("_", text)
    return text[:limit].strip("_")


def _header(request: Request, name: str) -> str:
    return _clean_identifier(request.headers.get(name, ""))


def _cookie(request: Request, name: str) -> str:
    return _clean_identifier(request.cookies.get(name, ""))


def resolve_user_id(request: Request) -> IdentityResolution:
    """Resolve the stable entity id used for memory and chat continuity.

    Priority:
    1) Authenticated account id header
    2) Session header/cookie id
    3) Device header/cookie id
    4) Local fallback id for zero-config development
    """
    account_id = _header(request, ACCOUNT_HEADER) or _header(request, AUTH_USER_HEADER)
    if account_id:
        return IdentityResolution(user_id=account_id, source="account_header")

    session_header_id = _header(request, SESSION_HEADER)
    session_cookie_id = _cookie(request, SESSION_COOKIE)
    if session_header_id:
        set_cookie = None if session_cookie_id == session_header_id else session_header_id
        return IdentityResolution(
            user_id=session_header_id,
            source="session_header",
            set_session_cookie=set_cookie,
        )
    if session_cookie_id:
        return IdentityResolution(user_id=session_cookie_id, source="session_cookie")

    device_header_id = _header(request, DEVICE_HEADER)
    device_cookie_id = _cookie(request, DEVICE_COOKIE)
    if device_header_id:
        set_cookie = None if device_cookie_id == device_header_id else device_header_id
        return IdentityResolution(
            user_id=device_header_id,
            source="device_header",
            set_device_cookie=set_cookie,
        )
    if device_cookie_id:
        return IdentityResolution(user_id=device_cookie_id, source="device_cookie")

    return IdentityResolution(user_id=LOCAL_FALLBACK_ENTITY, source="local_fallback")
