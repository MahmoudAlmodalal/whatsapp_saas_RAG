"""
app/database.py
───────────────
Async SQLAlchemy engine + session factory.

Design decisions:
- `asyncpg` driver for maximum async throughput.
- `NullPool` avoids pgbouncer/supabase pool conflicts (swap to AsyncAdaptedQueuePool
  for a dedicated DB host without a connection pooler).
- `get_db` yields a session and guarantees rollback on error.
- Multi-tenancy: callers must set `app.current_tenant` via `set_tenant_context()`
  before issuing any query.
"""
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,  # safe for Supabase PgBouncer; swap for long-lived pools
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base ORM class ────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this class."""
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a database session.
    Usage:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Multi-tenancy helper ──────────────────────────────────────────────────────
async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """
    Set the Postgres session-level variable used by Row-Level Security policies.
    Must be called once per request, after obtaining a session.

    Example usage in a middleware:
        await set_tenant_context(db, str(current_user.tenant_id))
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
