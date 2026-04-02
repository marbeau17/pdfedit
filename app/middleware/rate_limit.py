"""IP-based rate limiting middleware for API endpoints.

Uses an in-memory store that resets on serverless cold starts (acceptable).
Only rate-limits /api/* paths; static files and page routes are unaffected.
"""
from __future__ import annotations

import os
import time
import threading

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Defaults (overridable via env)
_DEFAULT_AI_LIMIT = 30
_DEFAULT_API_LIMIT = 100
_WINDOW_SECONDS = 60
_CLEANUP_INTERVAL = 120  # seconds between stale-entry sweeps


class _RateLimitStore:
    """Thread-safe in-memory store: IP -> (request_count, window_start)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[int, float]] = {}
        self._last_cleanup: float = time.monotonic()

    def check_and_increment(self, key: str, limit: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        If allowed is False, retry_after indicates how many seconds the
        client should wait before retrying.
        """
        now = time.monotonic()
        with self._lock:
            self._maybe_cleanup(now)
            count, window_start = self._data.get(key, (0, now))

            elapsed = now - window_start
            if elapsed >= _WINDOW_SECONDS:
                # New window
                self._data[key] = (1, now)
                return True, 0

            if count >= limit:
                retry_after = int(_WINDOW_SECONDS - elapsed) + 1
                return False, retry_after

            self._data[key] = (count + 1, window_start)
            return True, 0

    def _maybe_cleanup(self, now: float) -> None:
        """Remove entries whose window has expired."""
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        stale_keys = [
            k for k, (_, ws) in self._data.items()
            if now - ws >= _WINDOW_SECONDS
        ]
        for k in stale_keys:
            del self._data[k]


# Module-level singleton so the store persists across requests within the
# same serverless instance.
_store = _RateLimitStore()


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limits to /api/* endpoints.

    Parameters
    ----------
    app : ASGIApp
    ai_limit : int
        Max requests per minute for /api/ai/* routes.
    api_limit : int
        Max requests per minute for other /api/* routes.
    """

    def __init__(
        self,
        app: ASGIApp,
        ai_limit: int | None = None,
        api_limit: int | None = None,
    ) -> None:
        super().__init__(app)
        env_limit = os.environ.get("RATE_LIMIT_PER_MIN")
        default_ai = int(env_limit) if env_limit else _DEFAULT_AI_LIMIT
        self.ai_limit = ai_limit if ai_limit is not None else default_ai
        self.api_limit = api_limit if api_limit is not None else _DEFAULT_API_LIMIT

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only rate-limit API endpoints
        if not path.startswith("/api/"):
            return await call_next(request)

        ip = _get_client_ip(request)

        # Stricter limit for AI endpoints
        if path.startswith("/api/ai/"):
            limit = self.ai_limit
            key = f"ai:{ip}"
        else:
            limit = self.api_limit
            key = f"api:{ip}"

        allowed, retry_after = _store.check_and_increment(key, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
