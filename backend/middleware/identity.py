from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.identity.identity import DEVICE_COOKIE, SESSION_COOKIE, USER_HEADER, resolve_user_id


class IdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        identity = resolve_user_id(request)
        request.state.user_id = identity.user_id
        request.state.identity_source = identity.source

        response: Response = await call_next(request)
        response.headers[USER_HEADER] = identity.user_id
        response.headers["X-Friday-Identity-Source"] = identity.source
        secure = _is_secure_request(request)
        if identity.set_session_cookie:
            response.set_cookie(
                SESSION_COOKIE,
                identity.set_session_cookie,
                httponly=True,
                samesite="lax",
                secure=secure,
            )
        if identity.set_device_cookie:
            response.set_cookie(
                DEVICE_COOKIE,
                identity.set_device_cookie,
                httponly=True,
                samesite="lax",
                secure=secure,
            )
        return response


def _is_secure_request(request: Request) -> bool:
    proto = (request.headers.get("X-Forwarded-Proto") or request.url.scheme or "").strip().lower()
    return proto == "https"
