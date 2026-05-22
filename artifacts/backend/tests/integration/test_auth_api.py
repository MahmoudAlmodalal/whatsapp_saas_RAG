"""
tests/integration/test_auth_api.py
────────────────────────────────────
Integration tests for the authentication API endpoints.
Uses real DB (transaction-rolled-back), mocked external services.
Tests: login, refresh, RBAC, cross-tenant isolation, RLS enforcement.
"""
import pytest
from fastapi import status
from sqlalchemy import text

from app.core.security import create_refresh_token, create_access_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestLoginEndpoint:
    """POST /api/v1/auth/login"""

    async def test_login_success(self, client, agent_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "agent@test.sa", "password": "s3cret_agent"
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, agent_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "agent@test.sa", "password": "wrong_password"
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "البريد الإلكتروني أو كلمة المرور غير صحيحة" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@test.sa", "password": "doesntmatter"
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_inactive_user(self, client, db_session, agent_user):
        agent_user.is_active = False
        db_session.add(agent_user)
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "agent@test.sa", "password": "s3cret_agent"
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "الحساب موقوف" in resp.json()["detail"]

    async def test_login_missing_fields(self, client):
        resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.sa"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRefreshEndpoint:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client, agent_user):
        token = create_refresh_token(agent_user.id)
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access_token" in resp.json()

    async def test_refresh_invalid_token(self, client):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bad.token.here"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_with_access_token_rejected(self, client, agent_user):
        """Access tokens must be rejected as refresh tokens."""
        access = create_access_token(agent_user.id, agent_user.tenant_id, "agent")
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_suspended_user(self, client, db_session, agent_user):
        agent_user.is_active = False
        db_session.add(agent_user)
        await db_session.commit()

        token = create_refresh_token(agent_user.id)
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestProtectedEndpoints:
    """Access control for protected routes."""

    async def test_protected_endpoint_valid_jwt(self, client, admin_headers):
        resp = await client.get("/api/v1/tenants/me", headers=admin_headers)
        assert resp.status_code != status.HTTP_401_UNAUTHORIZED
        assert resp.status_code != status.HTTP_403_FORBIDDEN

    async def test_protected_endpoint_no_token(self, client):
        resp = await client.get("/api/v1/tenants/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_protected_endpoint_invalid_token(self, client):
        resp = await client.get("/api/v1/tenants/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_admin_only_endpoint_as_agent(self, client, agent_headers):
        """Agents must not access admin-only endpoints."""
        resp = await client.post("/api/v1/tenants/", headers=agent_headers, json={
            "name": "Unauthorized Tenant", "whatsapp_number": "+966500000001"
        })
        assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    async def test_rls_sets_tenant_context(self, db_session, admin_user):
        """Auth dependency must set app.current_tenant in PostgreSQL session."""
        from app.core.dependencies import get_current_admin
        await get_current_admin(current_user=admin_user, db=db_session)
        result = await db_session.execute(
            text("SELECT current_setting('app.current_tenant', true)")
        )
        assert result.scalar_one() == str(admin_user.tenant_id)


class TestCrossTenantIsolation:
    """Cross-tenant access must always be denied."""

    async def test_cross_tenant_document_access_denied(
        self, client, admin_headers, second_tenant, db_session
    ):
        """Admin of tenant A must not see tenant B's documents."""
        from app.models.documents import Document, DocumentStatus
        # Create document belonging to the second tenant
        doc = Document(
            tenant_id=second_tenant.id,
            file_name="سري.pdf",
            file_type="application/pdf",
            storage_path="uploads/secret.pdf",
            status=DocumentStatus.ready,
        )
        db_session.add(doc)
        await db_session.commit()

        # Tenant A admin tries to access it
        resp = await client.get(
            f"/api/v1/documents/{doc.id}",
            headers=admin_headers,
        )
        # Must return 404 (not found in tenant's scope) or 403
        assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
