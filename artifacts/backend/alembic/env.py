"""
alembic/env.py
──────────────
Async Alembic environment — required when using asyncpg / SQLAlchemy asyncio.

Key points:
- Reads DATABASE_URL from app.config (same source as the FastAPI app)
- Imports all models via app.database.Base so autogenerate works
- Uses asyncio.run() + run_sync() pattern for async migrations
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic config object ──────────────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ORM models so autogenerate can detect schema changes ────────────────
# This MUST happen before `target_metadata` is assigned.
from app.database import Base  # noqa: E402  (import after sys.path is set)
import app.models  # noqa: E402, F401 — side-effect: registers all models

target_metadata = Base.metadata

# ── Inject DATABASE_URL from pydantic-settings ────────────────────────────────
from app.config import get_settings  # noqa: E402

settings = get_settings()
# Convert asyncpg URL to asyncpg URL (keep as-is, alembic env runs async)
db_url = settings.DATABASE_URL
# Ensure we use asyncpg driver for async migrations
if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", db_url)


# ── Offline mode (generate SQL without a live DB) ─────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — produces a SQL script.
    Useful for auditing or applying migrations manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connect to DB and run migrations) ────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via run_sync()."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
