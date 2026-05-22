import pytest
from fastapi import HTTPException, status
from sqlalchemy import text
from app.core.security import create_refresh_token, create_access_token
from app.core.dependencies import get_current_user, get_current_admin, get_current_agent, get_current_operator

pytestmark = pytest.mark.asyncio


# ─── Auth Endpoint Tests ───

async def test_login_success(client, agent_user):
    """Verify that a user can log in successfully with valid credentials and receive tokens."""
    payload = {"email": "agent@test.sa", "password": "s3cret_agent"}
    response = await client.post("/api/v1/auth/login", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_credentials(client, agent_user):
    """Verify that wrong password returns HTTP 401 Unauthorized."""
    payload = {"email": "agent@test.sa", "password": "wrong_password"}
    response = await client.post("/api/v1/auth/login", json=payload)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "البريد الإلكتروني أو كلمة المرور غير صحيحة" in response.json()["detail"]


async def test_login_suspended_account(client, db_session, agent_user):
    """Verify that suspended user accounts cannot log in and receive an appropriate message."""
    agent_user.is_active = False
    db_session.add(agent_user)
    await db_session.commit()
    
    payload = {"email": "agent@test.sa", "password": "s3cret_agent"}
    response = await client.post("/api/v1/auth/login", json=payload)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "الحساب موقوف" in response.json()["detail"]


async def test_refresh_token_success(client, agent_user):
    """Verify that a valid refresh token generates a new access token successfully."""
    # Create valid refresh token
    refresh_token = create_refresh_token(agent_user.id)
    
    payload = {"refresh_token": refresh_token}
    response = await client.post("/api/v1/auth/refresh", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_refresh_token_invalid(client):
    """Verify that invalid refresh token returns HTTP 401 Unauthorized."""
    payload = {"refresh_token": "invalid_refresh_token"}
    response = await client.post("/api/v1/auth/refresh", json=payload)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "رمز التحديث غير صالح" in response.json()["detail"]


async def test_refresh_token_suspended_user(client, db_session, agent_user):
    """Verify that a suspended user cannot refresh their token."""
    agent_user.is_active = False
    db_session.add(agent_user)
    await db_session.commit()
    
    refresh_token = create_refresh_token(agent_user.id)
    payload = {"refresh_token": refresh_token}
    response = await client.post("/api/v1/auth/refresh", json=payload)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ─── Auth Dependency & RLS Context Tests ───

async def test_get_current_user_valid(db_session, agent_user):
    """Verify that get_current_user successfully returns the authenticated user object."""
    token = create_access_token(agent_user.id, agent_user.tenant_id, agent_user.role.value)
    user = await get_current_user(token=token, db=db_session)
    assert user.id == agent_user.id
    assert user.email == agent_user.email


async def test_get_current_user_inactive(db_session, agent_user):
    """Verify that get_current_user rejects deactivated users."""
    agent_user.is_active = False
    db_session.add(agent_user)
    await db_session.commit()
    
    token = create_access_token(agent_user.id, agent_user.tenant_id, agent_user.role.value)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "الحساب موقوف" in exc_info.value.detail


async def test_get_current_admin_rbac(db_session, admin_user, agent_user):
    """Verify that get_current_admin allows admins and rejects agents/operators."""
    # Should succeed for admin
    user, tenant_id = await get_current_admin(current_user=admin_user, db=db_session)
    assert user.id == admin_user.id
    assert tenant_id == admin_user.tenant_id
    
    # Should raise 403 for agent
    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(current_user=agent_user, db=db_session)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


async def test_get_current_admin_sets_rls_context(db_session, admin_user):
    """Verify that authenticated tenant dependencies set app.current_tenant."""
    await get_current_admin(current_user=admin_user, db=db_session)

    result = await db_session.execute(text("SELECT current_setting('app.current_tenant', true)"))
    assert result.scalar_one() == str(admin_user.tenant_id)


async def test_get_current_agent_rbac(db_session, admin_user, agent_user, operator_user):
    """Verify that get_current_agent allows admin/agent roles and rejects operators."""
    # Should succeed for admin
    user, tenant_id = await get_current_agent(current_user=admin_user, db=db_session)
    assert user.id == admin_user.id
    
    # Should succeed for agent
    user, tenant_id = await get_current_agent(current_user=agent_user, db=db_session)
    assert user.id == agent_user.id
    
    # Should raise 403 for operator
    with pytest.raises(HTTPException) as exc_info:
        await get_current_agent(current_user=operator_user, db=db_session)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


async def test_get_current_operator_rbac(db_session, operator_user, agent_user):
    """Verify that get_current_operator allows operators and rejects other roles."""
    # Should succeed for operator
    user, tenant_id = await get_current_operator(current_user=operator_user, db=db_session)
    assert user.id == operator_user.id
    
    # Should raise 403 for agent
    with pytest.raises(HTTPException) as exc_info:
        await get_current_operator(current_user=agent_user, db=db_session)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
