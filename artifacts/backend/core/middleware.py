"""
core/middleware.py
──────────────────
Rate-limiting middleware for the WhatsApp AI SaaS platform.

Two independent rate-limit tiers are enforced:

┌─────────────────────────────┬─────────────────────────────┬──────────────┐
│ Endpoint group              │ Key                         │ Limit        │
├─────────────────────────────┼─────────────────────────────┼──────────────┤
│ Dashboard API  /api/v1/…    │ per authenticated tenant_id │ 100 req/min  │
│ Webhook        /api/v1/…    │ per client IP address       │  30 req/min  │
└─────────────────────────────┴─────────────────────────────┴──────────────┘

Implementation
──────────────
- Uses ``slowapi`` (Starlette-compatible SlowAPI / limits library).
- Limiter is created once as a module-level singleton and attached to the
  FastAPI app via ``app.state.limiter`` + the SlowAPI exception handler.
- Individual route decorators apply the relevant tier.
- On limit breach slowapi raises a 429 Too Many Requests response with a
  ``Retry-After`` header (seconds until the window resets).

Registration (app/main.py)
──────────────────────────
    from core.middleware import limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

Usage on routes
───────────────
    from core.middleware import limiter, tenant_id_key, ip_key

    @router.post("/dashboard/something")
    @limiter.limit("100/minute", key_func=tenant_id_key)
    async def my_dashboard_endpoint(request: Request, ...):
        ...

    @router.post("/webhook")
    @limiter.limit("30/minute", key_func=ip_key)
    async def my_webhook_endpoint(request: Request, ...):
        ...
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Key extractor functions
# ─────────────────────────────────────────────────────────────────────────────


def tenant_id_key(request: Request) -> str:
    """
    Extract the tenant_id from the decoded JWT payload stored on request.state.

    Falls back to the client IP when no authenticated tenant is present
    (e.g., during the auth flow itself) so the limiter never crashes.

    The JWT dependency (app/core/dependencies.py) sets:
        request.state.tenant_id = str(payload["tenant_id"])
    after token validation.
    """
    tenant_id: str | None = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return f"tenant:{tenant_id}"
    # Fallback: use IP so unauthenticated requests are still rate-limited
    return f"ip:{get_remote_address(request)}"


def ip_key(request: Request) -> str:
    """
    Return the real client IP address as the rate-limit key.

    Trusts ``X-Forwarded-For`` (set by ALB / Nginx) when present, otherwise
    falls back to the direct connection address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; take the first IP
        ip = forwarded_for.split(",")[0].strip()
        return f"ip:{ip}"
    return f"ip:{get_remote_address(request)}"


# ─────────────────────────────────────────────────────────────────────────────
# Limiter singleton
# ─────────────────────────────────────────────────────────────────────────────

# Default key_func is IP-based; individual routes override with tenant_id_key
# where appropriate.
limiter = Limiter(key_func=ip_key, default_limits=[])

# ─────────────────────────────────────────────────────────────────────────────
# Convenience limit strings (import these into routers for consistency)
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_RATE_LIMIT = "100/minute"   # per authenticated tenant
WEBHOOK_RATE_LIMIT = "30/minute"      # per client IP

# ─────────────────────────────────────────────────────────────────────────────
# Custom 429 exception handler
# ─────────────────────────────────────────────────────────────────────────────


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Return a structured JSON 429 response with a Retry-After header.

    The ``Retry-After`` header value is the number of seconds until the
    current rate-limit window resets, as provided by slowapi.

    Response body (Arabic-first product):
    {
        "error":       "rate_limit_exceeded",
        "message":     "لقد تجاوزت الحد المسموح به من الطلبات…",
        "retry_after": <seconds>,
        "limit":       "<N>/minute"
    }
    """
    retry_after: int = getattr(exc, "retry_after", 60)
    limit_str: str = str(getattr(exc, "detail", "unknown"))

    logger.warning(
        "Rate limit exceeded — path=%s key=%s limit=%s retry_after=%ds",
        request.url.path,
        request.state.__dict__,
        limit_str,
        retry_after,
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": (
                f"لقد تجاوزت الحد المسموح به من الطلبات. "
                f"يرجى المحاولة مرة أخرى بعد {retry_after} ثانية."
            ),
            "retry_after": retry_after,
            "limit": limit_str,
        },
        headers={"Retry-After": str(retry_after)},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registration helper (called from app/main.py)
# ─────────────────────────────────────────────────────────────────────────────


def register_rate_limiting(app) -> None:  # type: ignore[no-untyped-def]
    """
    Attach the slowapi limiter and exception handler to the FastAPI *app*.

    Call this inside ``create_app()`` in ``app/main.py`` before including
    any routers so the limiter is available on ``app.state`` before routes
    are resolved.

    Example::

        from core.middleware import register_rate_limiting
        register_rate_limiting(app)
    """
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    logger.info("Rate limiting registered — dashboard=%s webhook=%s",
                DASHBOARD_RATE_LIMIT, WEBHOOK_RATE_LIMIT)
