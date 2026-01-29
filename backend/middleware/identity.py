from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.identity.identity import DEVICE_COOKIE, USER_HEADER, resolve_user_id


class IdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id, set_cookie = resolve_user_id(request)
        request.state.user_id = user_id

        response: Response = await call_next(request)
        response.headers[USER_HEADER] = user_id
        if set_cookie:
            response.set_cookie(
                DEVICE_COOKIE,
                user_id,
                httponly=True,
                samesite="lax",
            )
        return response
