import pytest
from uuid import uuid4
from fastapi import status
from app.core.cache import get_tenant_id_by_phone

pytestmark = pytest.mark.asyncio


# ─── Tenant Creation (Operator Only) ───

async def test_create_tenant_success(client, operator_headers):
    """Verify that an operator can successfully onboard a new tenant and seed Redis mapping."""
    payload = {
        "name": "شركة جديدة",
        "whatsapp_number": "+966599999999",
        "subscription_tier": "pro"
    }
    response = await client.post("/api/v1/tenants", json=payload, headers=operator_headers)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "شركة جديدة"
    assert data["whatsapp_number"] == "+966599999999"
    assert data["subscription_tier"] == "pro"
    
    # Check if the Redis mapping is properly seeded
    redis_tenant_id = await get_tenant_id_by_phone("+966599999999")
    assert redis_tenant_id == data["id"]


async def test_create_tenant_forbidden_for_admin_or_agent(client, admin_headers, agent_headers):
    """Verify that admins and agents are barred from tenant onboarding."""
    payload = {
        "name": "شركة محظورة",
        "whatsapp_number": "+966588888888",
        "subscription_tier": "basic"
    }
    
    # Rejects admin
    response = await client.post("/api/v1/tenants", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Rejects agent
    response = await client.post("/api/v1/tenants", json=payload, headers=agent_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_create_tenant_duplicate_whatsapp_number(client, operator_headers, test_tenant):
    """Verify that onboarding fails with HTTP 409 if the WhatsApp number is already registered."""
    payload = {
        "name": "شركة مكررة",
        "whatsapp_number": test_tenant.whatsapp_number,  # Already exists
        "subscription_tier": "basic"
    }
    response = await client.post("/api/v1/tenants", json=payload, headers=operator_headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "رقم الواتساب مسجل مسبقاً" in response.json()["detail"]


async def test_create_tenant_rejects_invalid_subscription_tier(client, operator_headers):
    """Verify tenant onboarding validates subscription_tier against the supported enum."""
    payload = {
        "name": "شركة بخطة غير صحيحة",
        "whatsapp_number": "+966577777777",
        "subscription_tier": "gold",
    }
    response = await client.post("/api/v1/tenants", json=payload, headers=operator_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ─── Tenant Retrieval (Admin Only) ───

async def test_get_tenant_details_success(client, admin_headers, test_tenant):
    """Verify that tenant admins can fetch their own tenant details."""
    response = await client.get(f"/api/v1/tenants/{test_tenant.id}", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_tenant.id)
    assert data["name"] == test_tenant.name


async def test_get_tenant_details_cross_tenant_isolation(client, admin_headers):
    """Verify that a tenant admin is forbidden from reading other tenants' details (RLS / access check)."""
    random_tenant_id = uuid4()
    response = await client.get(f"/api/v1/tenants/{random_tenant_id}", headers=admin_headers)
    
    # The endpoint validates user_tenant_id == path tenant_id and returns 403 if they don't match
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ─── Tenant Configuration (Admin Only) ───

async def test_update_tenant_config_success(client, admin_headers, test_tenant):
    """Verify that tenant admins can update their AI and handoff configuration."""
    payload = {
        "ai_persona_name": "مساعد ذكي جديد",
        "tone": "professional",
        "handoff_keywords": ["تحدث مع موظف", "مساعدة بشرية"],
        "confidence_threshold": 0.75,
        "max_context_turns": 15
    }
    response = await client.put(
        f"/api/v1/tenants/{test_tenant.id}/config",
        json=payload,
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["config"]["ai_persona_name"] == "مساعد ذكي جديد"
    assert data["config"]["tone"] == "professional"
    assert data["config"]["confidence_threshold"] == 0.75
    assert data["config"]["max_context_turns"] == 15


async def test_update_tenant_config_cross_tenant_isolation(client, admin_headers):
    """Verify that updating configuration is strictly isolated across tenants."""
    random_tenant_id = uuid4()
    payload = {"ai_persona_name": "اختراق"}
    response = await client.put(
        f"/api/v1/tenants/{random_tenant_id}/config",
        json=payload,
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ─── Tenant Suspension (Operator Only) ───

async def test_suspend_tenant_success(client, operator_headers, test_tenant, db_session):
    """Verify that an operator can successfully suspend a tenant."""
    response = await client.put(f"/api/v1/tenants/{test_tenant.id}/suspend", headers=operator_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Tenant suspended"
    
    # Reload and verify inside database
    await db_session.refresh(test_tenant)
    assert test_tenant.is_active is False


async def test_suspend_tenant_forbidden_for_admin(client, admin_headers, test_tenant):
    """Verify that a tenant admin cannot suspend any tenant (including their own)."""
    response = await client.put(f"/api/v1/tenants/{test_tenant.id}/suspend", headers=admin_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
