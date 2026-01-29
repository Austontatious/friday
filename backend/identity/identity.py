from __future__ import annotations

import uuid
from typing import Tuple

from fastapi import Request

DEVICE_HEADER = "X-Friday-Device"
USER_HEADER = "X-Friday-User"
DEVICE_COOKIE = "friday_device"


def resolve_user_id(request: Request) -> Tuple[str, bool]:
    """Return (user_id, set_cookie).

    Priority:
    1) X-Friday-Device header
    2) friday_device cookie
    3) generate new UUID and set cookie
    """
    header_id = request.headers.get(DEVICE_HEADER, "").strip()
    if header_id:
        return header_id, False

    cookie_id = request.cookies.get(DEVICE_COOKIE, "").strip()
    if cookie_id:
        return cookie_id, False

    new_id = uuid.uuid4().hex
    return new_id, True
