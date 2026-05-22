# ruff: noqa: E402
import asyncio
import os
import subprocess
import pytest
import pytest_asyncio
import asyncpg
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

# ─── Settings override before importing any app modules ───
from app import config

# We use a dedicated test DB and Redis index 9 to prevent polluting development databases.
base_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://whatsapp_user:whatsapp_pass@postgres:5432/whatsapp_saas",
)
test_db_url = base_db_url.replace("/whatsapp_saas", "/whatsapp_saas_test")
test_redis_url = "redis://redis:6379/9"

test_settings = config.Settings(
    ENVIRONMENT="test",
    DEBUG=False,
    DATABASE_URL=test_db_url,
    REDIS_URL=test_redis_url,
    CELERY_BROKER_URL="redis://redis:6379/10",
    CELERY_RESULT_BACKEND="redis://redis:6379/11",
    SECRET_KEY="test-secret-key-12345",
    WHATSAPP_VERIFY_TOKEN="test-verify-token",
    WHATSAPP_APP_SECRET="test-app-secret-67890"
)

# Patch the cached settings singleton
config.get_settings = lambda: test_settings

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from app.database import get_db
from app.main import app as fastapi_app
from app.models.tenants import Tenant
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token


async def create_test_db_if_not_exists():
    """Connect to default postgres DB and create whatsapp_saas_test if needed."""
    settings = config.get_settings()
    # Extract base connection url targeting default whatsapp_saas db to run CREATE DATABASE
    conn_url = settings.DATABASE_URL.replace("/whatsapp_saas_test", "/whatsapp_saas")
    url_for_asyncpg = conn_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        conn = await asyncpg.connect(url_for_asyncpg)
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'whatsapp_saas_test'"
        )
        if not exists:
            # CREATE DATABASE cannot run within transactions
            await conn.execute("COMMIT")
            await conn.execute("CREATE DATABASE whatsapp_saas_test")
            print("Successfully created test database 'whatsapp_saas_test'.")
        await conn.close()
    except Exception as e:
        print(f"Warning/Error creating test database: {e}")


def run_alembic_migrations():
    """Execute Alembic migrations programmatically against the test database."""
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    env["REDIS_URL"] = test_redis_url
    env["SECRET_KEY"] = "test-secret-key-12345"
    env["ENVIRONMENT"] = "test"
    env["DEBUG"] = "false"
    env["WHATSAPP_VERIFY_TOKEN"] = "test-verify-token"
    env["WHATSAPP_APP_SECRET"] = "test-app-secret-67890"
    subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)


def pytest_sessionstart(session):
    """pytest hook run at start of test session: prepares test DB."""
    asyncio.run(create_test_db_if_not_exists())
    run_alembic_migrations()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Function-scoped async SQLAlchemy engine."""
    engine = create_async_engine(test_db_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped session which rolls back all transactions after each test case."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    
    AsyncSessionLocal = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as session:
        # Override get_db dependency in the FastAPI application
        async def override_get_db():
            yield session
            
        fastapi_app.dependency_overrides[get_db] = override_get_db
        yield session
        
        # Clean up dependency override
        fastapi_app.dependency_overrides.pop(get_db, None)
        
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Function-scoped httpx async test client targeting FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def clean_redis():
    """Flushes test Redis DB index 9 before every test to ensure strict isolation."""
    import redis.asyncio as redis
    from app.core.cache import redis_client as global_redis
    
    # Reset global Redis client connection pool to adapt to the current event loop
    await global_redis.connection_pool.disconnect()
    
    settings = config.get_settings()
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    await client.flushdb()
    await client.aclose()


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Mocks Celery delay task execution globally to isolate task queues."""
    with patch("tasks.message_tasks.process_inbound_message.delay") as mock_delay:
        yield mock_delay


# ─── Model Helper Fixtures ───

@pytest_asyncio.fixture
async def test_tenant(db_session) -> Tenant:
    """Create and return a default tenant."""
    tenant = Tenant(
        name="مؤسسة التقنية للتجربة",
        whatsapp_number="+966501234567",
        subscription_tier="basic",
        config={
            "ai_persona_name": "مساعد تجريبي",
            "language": "arabic",
            "tone": "friendly",
            "handoff_keywords": ["تكلم مع موظف", "إنسان"],
            "confidence_threshold": 0.5,
            "max_context_turns": 5
        }
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    
    # Also seed Redis phone mapping for integration test validation
    from app.core.cache import set_tenant_phone_mapping
    await set_tenant_phone_mapping(tenant.whatsapp_number, str(tenant.id))
    
    return tenant


@pytest_asyncio.fixture
async def admin_user(db_session, test_tenant) -> User:
    """Create and return an admin user belonging to the test tenant."""
    user = User(
        tenant_id=test_tenant.id,
        email="admin@test.sa",
        hashed_password=hash_password("s3cret_admin"),
        role=UserRole.admin,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def agent_user(db_session, test_tenant) -> User:
    """Create and return an agent user belonging to the test tenant."""
    user = User(
        tenant_id=test_tenant.id,
        email="agent@test.sa",
        hashed_password=hash_password("s3cret_agent"),
        role=UserRole.agent,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def operator_user(db_session, test_tenant) -> User:
    """Create and return an operator user belonging to the test tenant."""
    user = User(
        tenant_id=test_tenant.id,
        email="operator@test.sa",
        hashed_password=hash_password("s3cret_operator"),
        role=UserRole.operator,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ─── Auth Header Helpers ───

@pytest.fixture
def admin_headers(admin_user) -> dict[str, str]:
    """Generate JWT headers for the admin user."""
    token = create_access_token(admin_user.id, admin_user.tenant_id, admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_headers(agent_user) -> dict[str, str]:
    """Generate JWT headers for the agent user."""
    token = create_access_token(agent_user.id, agent_user.tenant_id, agent_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(operator_user) -> dict[str, str]:
    """Generate JWT headers for the operator user."""
    token = create_access_token(operator_user.id, operator_user.tenant_id, operator_user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ─── Celery Eager Mode ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def celery_eager_mode():
    """
    Force Celery to execute tasks synchronously (inline) during tests.
    This bypasses the message broker entirely and runs tasks in-process.
    Combine with `mock_celery_task` override when testing dispatch-only flows.
    """
    from celery_app import celery_app
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


# ─── External Service Mocks ───────────────────────────────────────────────────

@pytest.fixture
def mock_whatsapp_sender(mocker):
    """
    Mock the WhatsApp outbound sender to prevent real API calls during tests.
    Returns the mock so tests can assert call arguments.
    """
    mock = mocker.patch(
        "app.services.whatsapp_sender.WhatsAppSender.send_text_message",
        new_callable=AsyncMock,
        return_value={"messages": [{"id": "wamid.test123"}]},
    )
    return mock


@pytest.fixture
def mock_llm_response(mocker):
    """
    Mock DeepSeek LLM API to return a deterministic Arabic response.
    Prevents network calls and ensures reproducible test assertions.
    """
    mock = mocker.patch(
        "app.services.llm_orchestrator.LLMOrchestrator.generate_response",
        new_callable=AsyncMock,
        return_value={
            "response": "أهلاً بك! يسعدني مساعدتك في استفساراتك.",
            "cached": False,
            "tokens_used": 150,
            "latency_ms": 320,
        },
    )
    return mock


@pytest.fixture
def mock_embedding_model(mocker):
    """
    Mock the sentence-transformers embedding model to avoid loading a 1.8GB model
    during CI/unit tests. Returns a fixed 1024-dim zero vector.
    """
    import numpy as np
    mock = mocker.patch(
        "app.services.ingestion.get_embedding_model",
    )
    mock_model = mocker.MagicMock()
    mock_model.encode.return_value = np.zeros((1, 1024), dtype=np.float32)
    mock.return_value = mock_model
    return mock_model


# ─── Second Tenant (Cross-Tenant Isolation Tests) ─────────────────────────────

@pytest_asyncio.fixture
async def second_tenant(db_session) -> "Tenant":
    """Create a second tenant for cross-tenant isolation testing."""
    tenant = Tenant(
        name="مؤسسة أخرى للتجربة",
        whatsapp_number="+966509999999",
        subscription_tier="pro",
        config={
            "ai_persona_name": "مساعد آخر",
            "language": "arabic",
            "tone": "professional",
            "handoff_keywords": ["موظف"],
            "confidence_threshold": 0.6,
            "max_context_turns": 5,
        },
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant
