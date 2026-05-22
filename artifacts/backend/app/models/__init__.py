"""
app/models/__init__.py
───────────────────────
Re-export all ORM models so that:
  1. `from app.models import Tenant, Conversation, ...` works anywhere.
  2. Alembic's `env.py` sees every model when it does `import app.models`,
     which is required for `--autogenerate` to detect schema changes.

Import order matters — Tenant must be registered before its FK dependants.
"""

from app.models.tenants import Tenant, SubscriptionTier
from app.models.user import User, UserRole
from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message, MessageRole
from app.models.documents import Document, DocumentStatus
from app.models.document_chunks import DocumentChunk

__all__ = [
    # Models
    "Tenant",
    "User",
    "Conversation",
    "Message",
    "Document",
    "DocumentChunk",
    # Enums (useful for schema / API layers)
    "SubscriptionTier",
    "UserRole",
    "ConversationStatus",
    "MessageRole",
    "DocumentStatus",
]
