import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status

pytestmark = pytest.mark.asyncio


async def test_liveness_probe(client):
    """Verify that /health liveness probe returns HTTP 200 and 'ok' status."""
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "whatsapp-saas"
    assert "environment" in data
    assert "uptime_seconds" in data


async def test_readiness_probe_healthy(client):
    """Verify that /ready returns HTTP 200 and 'ready' status when database and Redis are up."""
    response = await client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["postgres"] == "ok"
    assert data["checks"]["redis"] == "ok"


async def test_readiness_probe_postgres_degraded(client):
    """Verify that /ready returns HTTP 503 degraded when PostgreSQL connection fails."""
    # Patch AsyncSessionLocal execute to raise an error
    with patch("app.core.health.AsyncSessionLocal") as mock_session_class:
        mock_session = mock_session_class.return_value.__aenter__.return_value
        mock_session.execute.side_effect = Exception("DB Connection Lost")
        
        response = await client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert "error" in data["checks"]["postgres"]
        assert data["checks"]["redis"] == "ok"


async def test_readiness_probe_redis_degraded(client):
    """Verify that /ready returns HTTP 503 degraded when Redis connection fails."""
    # Patch aioredis.from_url to return a client whose ping raises an error
    with patch("app.core.health.aioredis.from_url") as mock_from_url:
        mock_client = mock_from_url.return_value
        mock_client.ping.side_effect = Exception("Redis connection timeout")
        mock_client.aclose = AsyncMock()
        
        response = await client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["postgres"] == "ok"
        assert "error" in data["checks"]["redis"]
