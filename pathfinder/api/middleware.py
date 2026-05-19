"""Cross-cutting middleware for Pathfinder V1 API.

Provides:
  (1) Audit whitelist checker — warns if POST/PUT/DELETE produced 0 audit events.
  (2) Default-deny auth dependency — unmarked endpoints require admin token.
  (3) Simple rate limit middleware — 100 req/min per key, configurable.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from pathfinder.api.schemas import ApiError

logger = logging.getLogger("pathfinder.middleware")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _auth_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=ApiError(error="AUTH_REQUIRED", detail=detail).model_dump(),
    )


def _forbidden_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=ApiError(error="FORBIDDEN", detail=detail).model_dump(),
    )


def _rate_limited(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": ApiError(error="RATE_LIMITED", detail=detail).model_dump()},
    )


def _extract_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# (1) Audit whitelist checker middleware
# ──────────────────────────────────────────────────────────────────────────────

class AuditWhitelistMiddleware:
    """Warns if a POST/PUT/DELETE request produced zero audit events.

    Checks the audit event count before and after the request.  If the count
    did not increase and the method is a mutating one, a warning is logged.
    """

    def __init__(self, app, get_service: Callable):
        self.app = app
        self._get_service = get_service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        if method not in ("POST", "PUT", "DELETE"):
            await self.app(scope, receive, send)
            return

        # Snapshot audit count before handling.
        try:
            service = self._get_service()
            count_before = len(service.audit_log.events())
        except Exception:
            count_before = 0

        await self.app(scope, receive, send)

        try:
            service = self._get_service()
            count_after = len(service.audit_log.events())
        except Exception:
            count_after = 0

        if count_after == count_before:
            path = scope.get("path", "?")
            logger.warning(
                "audit-whitelist: %s %s produced 0 audit events — "
                "endpoint may be missing audit logging",
                method,
                path,
            )


# ──────────────────────────────────────────────────────────────────────────────
# (2) Default-deny auth dependency / middleware
# ──────────────────────────────────────────────────────────────────────────────

# Endpoint path prefixes that are allowed with demo token.
_DEMO_ALLOWED_PREFIXES = (
    "/v1/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Endpoint paths accessible without any token.
_PUBLIC_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
})


def require_demo_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency: require demo token (or admin token)."""
    import os

    admin_token = os.environ.get(
        "PATHFINDER_ADMIN_TOKEN",
        "admin-token" if os.environ.get("ENVIRONMENT", "development").lower() != "production" else "",
    )
    demo_token = os.environ.get(
        "PATHFINDER_DEMO_TOKEN",
        "demo-token" if os.environ.get("ENVIRONMENT", "development").lower() != "production" else "",
    )
    if authorization not in {f"Bearer {demo_token}", f"Bearer {admin_token}"}:
        raise _auth_error("invited demo token required")


def require_admin_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency: require admin token."""
    import os

    admin_token = os.environ.get(
        "PATHFINDER_ADMIN_TOKEN",
        "admin-token" if os.environ.get("ENVIRONMENT", "development").lower() != "production" else "",
    )
    if authorization != f"Bearer {admin_token}":
        raise _forbidden_error("admin token required")


class DefaultDenyAuthMiddleware:
    """FastAPI ASGI middleware that applies default-deny auth policy.

    - Public paths (health, docs) pass through without auth.
    - Admin token grants access to everything.
    - Demo token grants access to /v1/* routes only.
    - All other requests → 401 (default-deny).
    """

    def __init__(self, app, admin_token: str, demo_token: str):
        self.app = app
        # Reject empty tokens (prevents Bearer="" matching any empty auth header)
        if not admin_token or not demo_token:
            raise ValueError(
                "DefaultDenyAuthMiddleware requires non-empty admin_token and demo_token. "
                "Set PATHFINDER_ADMIN_TOKEN and PATHFINDER_DEMO_TOKEN environment variables."
            )
        self._admin_auth = f"Bearer {admin_token}"
        self._demo_auth = f"Bearer {demo_token}"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Normalize: strip trailing slash for public path matching
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")

        # Public paths always allowed.
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # Scan headers for Authorization.
        auth: str = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == b"authorization":
                auth = header_value.decode("latin-1", errors="replace")
                break

        # Fallback: accept ?token= from query string (browser-friendly HTML viz)
        if not auth:
            qs = scope.get("query_string", b"")
            if qs:
                from urllib.parse import parse_qs
                params = parse_qs(qs.decode("latin-1", errors="replace"))
                token_vals = params.get("token", [])
                if token_vals and token_vals[0]:
                    auth = f"Bearer {token_vals[0]}"

        # Admin token → full access.
        if auth == self._admin_auth:
            await self.app(scope, receive, send)
            return

        # Demo token → restricted to /v1/ routes.
        if auth == self._demo_auth:
            if path.startswith(_DEMO_ALLOWED_PREFIXES):
                await self.app(scope, receive, send)
                return
            # Demo token tried to access a non-demo route.
            await self._send_error(
                send, 403, ApiError(error="FORBIDDEN", detail="admin token required").model_dump()
            )
            return

        # No valid token → 401 default-deny.
        await self._send_error(
            send, 401, ApiError(error="AUTH_REQUIRED", detail="authentication required").model_dump()
        )

    async def _send_error(self, send, status_code: int, detail: dict) -> None:
        import json

        body = json.dumps({"detail": detail}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


# ──────────────────────────────────────────────────────────────────────────────
# (3) Simple rate-limit middleware
# ──────────────────────────────────────────────────────────────────────────────

class RateLimitMiddleware:
    """Rate-limit middleware: 100 req/min per (auth_token, ip) key by default.

    Configurable via PATHFINDER_RATE_LIMIT_MAX and
    PATHFINDER_RATE_LIMIT_WINDOW_SECONDS environment variables.
    """

    def __init__(
        self,
        app,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ):
        import os

        self.app = app
        self.max_requests = max_requests or int(
            os.environ.get("PATHFINDER_RATE_LIMIT_MAX", "100")
        )
        self.window_seconds = window_seconds or int(
            os.environ.get("PATHFINDER_RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self._hits: dict[str, tuple[int, float]] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        # Never rate-limit health checks or docs.
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        now = time.monotonic()

        # Build key from authorization + ip.
        auth: str = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == b"authorization":
                auth = header_value.decode("latin-1", errors="replace")
                break

        ip = _extract_ip_from_scope(scope)
        key = f"{auth}:{ip}"

        count, window_start = self._hits.get(key, (0, now))
        if now - window_start >= self.window_seconds:
            count = 0
            window_start = now
        count += 1
        self._hits[key] = (count, window_start)

        if count > self.max_requests:
            await self._send_error(send)
            return

        await self.app(scope, receive, send)

    async def _send_error(self, send) -> None:
        import json

        body = json.dumps({
            "detail": ApiError(
                error="RATE_LIMITED", detail="too many requests"
            ).model_dump()
        }).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

    def clear(self) -> None:
        """Reset rate-limit counters (useful in tests)."""
        self._hits.clear()


def _extract_ip_from_scope(scope) -> str:
    """Extract client IP from ASGI scope."""
    # Check x-forwarded-for in headers.
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == b"x-forwarded-for":
            return header_value.decode("latin-1", errors="replace").split(",", 1)[0].strip()

    # Check client tuple.
    client = scope.get("client")
    if client:
        return client[0]

    return "unknown"
