"""
app/main.py
───────────
FastAPI application entrypoint.

Startup checklist:
- CORS configured for development (tighten origins in production)
- /health and /ready registered at root level (no version prefix — k8s/ALB probes need them)
- API v1 router placeholder ready for future routers
- Lifespan context manager for clean startup/shutdown hooks
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqladmin import Admin

from app.config import get_settings
from app.database import engine as db_engine
from core.middleware import register_rate_limiting
from app.core.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.handoff import router as handoff_router
from app.routers.tenants import router as tenants_router
from app.routers.webhook import router as webhook_router
from app.admin.auth import AdminAuth
from app.admin.views import ALL_ADMIN_VIEWS

settings = get_settings()


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Code before `yield` runs at startup.
    Code after `yield` runs at shutdown.
    Add DB pool warm-up, background task init, etc. here.
    """
    # Startup
    print(f"🚀  Starting {settings.APP_NAME} [{settings.ENVIRONMENT}]")
    yield
    # Shutdown
    print(f"🛑  Shutting down {settings.APP_NAME}")


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Multi-tenant WhatsApp AI SaaS — Arabic SMB platform.\n\n"
            "All endpoints require a valid JWT Bearer token except `/health` and `/ready`."
        ),
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    origins = (
        ["*"]
        if settings.ENVIRONMENT == "development"
        else [
            # Add your production frontend domains here
            "https://app.yourdomain.com",
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Session middleware (required for admin panel cookie auth) ─────────────
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="admin_session",
        max_age=60 * 60 * 8,  # 8-hour session
        https_only=settings.is_production,
        same_site="lax",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    register_rate_limiting(app)

    # ── Admin Panel (/admin) ──────────────────────────────────────────────────
    admin = Admin(
        app,
        engine=db_engine,
        base_url="/admin",
        title="WhatsApp SaaS — Super Admin",
        logo_url="https://fastapi.tiangolo.com/img/favicon.png",
        authentication_backend=AdminAuth(secret_key=settings.SECRET_KEY),
    )
    for view in ALL_ADMIN_VIEWS:
        admin.add_view(view)

    # ── Routers ───────────────────────────────────────────────────────────────
    # Health probes — no prefix so k8s / load-balancers can hit them directly
    app.include_router(health_router)

    # Versioned API
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tenants_router, prefix="/api/v1/tenants")
    app.include_router(documents_router, prefix="/api/v1/tenants")
    app.include_router(handoff_router, prefix="/api/v1/tenants")
    app.include_router(webhook_router, prefix="/api/v1")

    return app


app = create_app()
