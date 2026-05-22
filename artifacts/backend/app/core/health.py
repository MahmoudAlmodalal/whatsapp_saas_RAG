"""
app/core/health.py
──────────────────
/health  → lightweight liveness probe (no I/O)
/ready   → readiness probe — verifies DB + Redis connectivity

Returns HTTP 200 when healthy, HTTP 503 when any dependency is down.
"""
import time

import redis.asyncio as aioredis
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal

router = APIRouter(tags=["Health"])
settings = get_settings()

_START_TIME = time.time()


@router.get(
    "/health",
    summary="Liveness probe",
    response_description="Service is alive",
)
async def health() -> dict:
    """
    Lightweight liveness check — no database or cache I/O.
    Kubernetes / Docker use this to decide whether to restart the container.
    """
    return {
        "status": "ok",
        "service": "whatsapp-saas",
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }


@router.get(
    "/ready",
    summary="Readiness probe",
    response_description="Service is ready to receive traffic",
)
async def ready() -> JSONResponse:
    """
    Readiness check — verifies that PostgreSQL and Redis are reachable.
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    checks: dict[str, str] = {}
    healthy = True

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        healthy = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    # Client is created OUTSIDE try so finally can always call aclose().
    # Previously aclose() was only reached on the happy path → connection leak
    # on every failed probe.
    client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
    try:
        await client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False
    finally:
        await client.aclose()   # always released — success or failure

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if healthy else "degraded",
            "checks": checks,
        },
    )
