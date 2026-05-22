"""
tests/factories/conversation_factory.py
────────────────────────────────────────
ConversationFactory — generates test Conversation instances.

Supports all lifecycle statuses: active, handoff, closed.
"""
import uuid
from datetime import datetime, timezone
import factory

from app.models.conversations import Conversation, ConversationStatus


class ConversationFactory(factory.Factory):
    """Factory for generating Conversation instances."""

    class Meta:
        model = Conversation

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)
    customer_phone = factory.Sequence(lambda n: f"+9665{str(n + 10000000).zfill(8)}")
    status = ConversationStatus.active
    ai_mode = True
    started_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    last_message_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    meta_data = factory.LazyFunction(
        lambda: {
            "customer_name": "عميل تجريبي",
            "source_channel": "whatsapp",
            "tags": [],
        }
    )

    class Params:
        """Status variants."""

        active = factory.Trait(status=ConversationStatus.active, ai_mode=True)
        handoff = factory.Trait(status=ConversationStatus.handoff, ai_mode=False)
        closed = factory.Trait(status=ConversationStatus.closed, ai_mode=False)
        ai_disabled = factory.Trait(ai_mode=False)
