"""
tests/integration/test_handoff_flow.py
────────────────────────────────────────
Integration tests for the complete human handoff workflow:
- AI triggers handoff (keyword detection)
- Agent accepts handoff
- Agent sends direct reply
- AI re-enabled by admin
- Handoff cancellation
"""
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.conversations import Conversation, ConversationStatus

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _create_active_conversation(db_session, tenant, customer_phone="+966507654321"):
    """Helper: seed an active AI-mode conversation."""
    conv = Conversation(
        tenant_id=tenant.id,
        customer_phone=customer_phone,
        status=ConversationStatus.active,
        ai_mode=True,
        meta_data={"customer_name": "عميل تجريبي"},
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


class TestHandoffTrigger:
    """Tests for handoff initiation endpoints."""

    async def test_trigger_handoff_sets_status(
        self, client, db_session, admin_headers, test_tenant
    ):
        conv = await _create_active_conversation(db_session, test_tenant)

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/trigger",
            headers=admin_headers,
        )
        assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

        await db_session.refresh(conv)
        assert conv.status == ConversationStatus.handoff
        assert conv.ai_mode is False

    async def test_trigger_handoff_on_nonexistent_conversation(
        self, client, admin_headers
    ):
        import uuid
        resp = await client.post(
            f"/api/v1/handoff/{uuid.uuid4()}/trigger",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_trigger_handoff_requires_auth(self, client, db_session, test_tenant):
        conv = await _create_active_conversation(db_session, test_tenant)
        resp = await client.post(f"/api/v1/handoff/{conv.id}/trigger")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestHandoffAccept:
    """Tests for agent accepting a handoff."""

    async def test_agent_accepts_handoff(
        self, client, db_session, agent_headers, test_tenant, agent_user
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        # First trigger it
        conv.status = ConversationStatus.handoff
        conv.ai_mode = False
        db_session.add(conv)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/accept",
            headers=agent_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    async def test_operator_cannot_accept_handoff(
        self, client, db_session, operator_headers, test_tenant
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        conv.status = ConversationStatus.handoff
        conv.ai_mode = False
        db_session.add(conv)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/accept",
            headers=operator_headers,
        )
        assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


class TestAgentReply:
    """Tests for agent sending messages directly to customer."""

    async def test_agent_reply_in_handoff_mode(
        self, client, db_session, agent_headers, test_tenant, mock_whatsapp_sender
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        conv.status = ConversationStatus.handoff
        conv.ai_mode = False
        db_session.add(conv)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/reply",
            headers=agent_headers,
            json={"message": "مرحباً، أنا وكيل الدعم. كيف يمكنني مساعدتك؟"},
        )
        assert resp.status_code == status.HTTP_200_OK

    async def test_agent_cannot_reply_on_ai_conversation(
        self, client, db_session, agent_headers, test_tenant
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        # AI mode is True — agent must not reply
        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/reply",
            headers=agent_headers,
            json={"message": "رسالة من الوكيل"},
        )
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_409_CONFLICT,
        )


class TestAIReEnable:
    """Tests for re-enabling AI mode after handoff."""

    async def test_admin_re_enables_ai(
        self, client, db_session, admin_headers, test_tenant
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        conv.status = ConversationStatus.handoff
        conv.ai_mode = False
        db_session.add(conv)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/reenable",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

        await db_session.refresh(conv)
        assert conv.ai_mode is True
        assert conv.status == ConversationStatus.active

    async def test_agent_cannot_reenable_ai(
        self, client, db_session, agent_headers, test_tenant
    ):
        conv = await _create_active_conversation(db_session, test_tenant)
        conv.ai_mode = False
        db_session.add(conv)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/handoff/{conv.id}/reenable",
            headers=agent_headers,
        )
        assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
