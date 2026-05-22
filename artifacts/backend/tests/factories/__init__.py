"""
tests/factories/__init__.py
────────────────────────────
factory_boy data factories for the WhatsApp AI SaaS test suite.

Usage example:
    from tests.factories import TenantFactory, UserFactory, ConversationFactory

    tenant = TenantFactory.build()          # in-memory, no DB
    tenant = await TenantFactory.create()   # async DB insert
"""
from tests.factories.tenant_factory import TenantFactory
from tests.factories.user_factory import UserFactory
from tests.factories.conversation_factory import ConversationFactory
from tests.factories.message_factory import MessageFactory
from tests.factories.document_factory import DocumentFactory

__all__ = [
    "TenantFactory",
    "UserFactory",
    "ConversationFactory",
    "MessageFactory",
    "DocumentFactory",
]
