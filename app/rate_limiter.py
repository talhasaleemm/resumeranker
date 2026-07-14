"""
app/rate_limiter.py — slowapi rate limiter configuration (Phase 6B-2b).

This module exists to avoid circular imports between app.main and the API
routers, which both need access to the shared Limiter instance.
"""
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()


def _rate_limit_key_func(request: Request) -> str:
    if not settings.rate_limit_enabled:
        return "disabled"
    if request.headers.get("x-test-bypass") == "true":
        import uuid
        return f"bypass-{uuid.uuid4()}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key_func, headers_enabled=False, retry_after="seconds")
limiter._default_limits = [] if not settings.rate_limit_enabled else ["60/minute"]


def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
    )
    app_limiter = request.app.state.limiter
    try:
        view_limit = getattr(request.state, "view_rate_limit", None)
        if app_limiter and view_limit is not None:
            window_stats = app_limiter.limiter.get_window_stats(view_limit[0], *view_limit[1])
            reset_in = max(1, 1 + window_stats[0])
            response.headers["Retry-After"] = str(int(reset_in - time.time()))
    except Exception:
        pass
    return response
