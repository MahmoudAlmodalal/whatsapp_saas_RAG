"""
app/admin/views.py
───────────────────
SQLAdmin model views — defines what the super admin can see and edit
in the admin panel for each database table.

Registered views:
  - TenantAdmin    → /admin/tenant/     (full CRUD + search + filter)
  - UserAdmin      → /admin/user/       (full CRUD + role filter)
  - DocumentAdmin  → /admin/document/   (read + status filter)
  - ConversationAdmin → /admin/conversation/ (read + status filter)
  - MessageAdmin   → /admin/message/    (read-only)
"""
from sqladmin import ModelView
from wtforms import validators

from app.models.tenants import Tenant, SubscriptionTier
from app.models.user import User, UserRole
from app.models.documents import Document, DocumentStatus
from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message


# ─── Tenant Admin ─────────────────────────────────────────────────────────────

class TenantAdmin(ModelView, model=Tenant):
    # ── Display ──────────────────────────────────────────────────────────────
    name = "Tenant"
    name_plural = "Tenants"
    icon = "fa-solid fa-building"

    # ── List view columns ────────────────────────────────────────────────────
    column_list = [
        Tenant.id,
        Tenant.name,
        Tenant.whatsapp_number,
        Tenant.subscription_tier,
        Tenant.is_active,
        Tenant.created_at,
    ]
    column_searchable_list = [Tenant.name, Tenant.whatsapp_number]
    column_sortable_list = [Tenant.name, Tenant.subscription_tier, Tenant.created_at]
    column_filters = [Tenant.subscription_tier, Tenant.is_active]

    # ── Detail view ──────────────────────────────────────────────────────────
    column_details_list = [
        Tenant.id,
        Tenant.name,
        Tenant.whatsapp_number,
        Tenant.subscription_tier,
        Tenant.is_active,
        Tenant.config,
        Tenant.created_at,
        Tenant.updated_at,
    ]

    # ── Form (create / edit) ─────────────────────────────────────────────────
    form_columns = [
        Tenant.name,
        Tenant.whatsapp_number,
        Tenant.subscription_tier,
        Tenant.is_active,
        Tenant.config,
    ]
    form_include_pk = False

    # ── Permissions ──────────────────────────────────────────────────────────
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True

    # ── Export ───────────────────────────────────────────────────────────────
    export_types = ["csv", "json"]
    export_max_rows = 1000

    # ── Page size ────────────────────────────────────────────────────────────
    page_size = 25
    page_size_options = [10, 25, 50, 100]


# ─── User Admin ───────────────────────────────────────────────────────────────

class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"

    column_list = [
        User.id,
        User.email,
        User.role,
        User.is_active,
        User.tenant_id,
        User.created_at,
    ]
    column_searchable_list = [User.email]
    column_sortable_list = [User.email, User.role, User.created_at]
    column_filters = [User.role, User.is_active]

    column_details_list = [
        User.id,
        User.email,
        User.role,
        User.is_active,
        User.tenant_id,
        User.created_at,
        User.updated_at,
    ]

    # ── Form: never expose hashed_password in the form ───────────────────────
    form_columns = [
        User.email,
        User.role,
        User.is_active,
        User.tenant_id,
    ]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True

    export_types = ["csv"]
    page_size = 25


# ─── Document Admin ───────────────────────────────────────────────────────────

class DocumentAdmin(ModelView, model=Document):
    name = "Document"
    name_plural = "Documents"
    icon = "fa-solid fa-file-alt"

    column_list = [
        Document.id,
        Document.file_name,
        Document.file_type,
        Document.status,
        Document.chunk_count,
        Document.tenant_id,
        Document.uploaded_at,
    ]
    column_searchable_list = [Document.file_name]
    column_sortable_list = [Document.file_name, Document.status, Document.uploaded_at]
    column_filters = [Document.status, Document.file_type]

    column_details_list = [
        Document.id,
        Document.file_name,
        Document.file_type,
        Document.storage_path,
        Document.status,
        Document.chunk_count,
        Document.tenant_id,
        Document.uploaded_at,
        Document.processed_at,
        Document.meta_data,
    ]

    # Documents: allow status override + deletion only; no create via admin
    can_create = False
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True

    form_columns = [Document.status]  # only allow status edits
    page_size = 25


# ─── Conversation Admin ────────────────────────────────────────────────────────

class ConversationAdmin(ModelView, model=Conversation):
    name = "Conversation"
    name_plural = "Conversations"
    icon = "fa-solid fa-comments"

    column_list = [
        Conversation.id,
        Conversation.customer_phone,
        Conversation.status,
        Conversation.ai_mode,
        Conversation.tenant_id,
        Conversation.started_at,
        Conversation.last_message_at,
    ]
    column_searchable_list = [Conversation.customer_phone]
    column_sortable_list = [
        Conversation.status,
        Conversation.started_at,
        Conversation.last_message_at,
    ]
    column_filters = [Conversation.status, Conversation.ai_mode]

    column_details_list = [
        Conversation.id,
        Conversation.tenant_id,
        Conversation.customer_phone,
        Conversation.status,
        Conversation.ai_mode,
        Conversation.started_at,
        Conversation.last_message_at,
        Conversation.meta_data,
    ]

    can_create = False
    can_edit = True   # allow toggling ai_mode or status
    can_delete = True
    can_view_details = True
    can_export = True

    form_columns = [Conversation.status, Conversation.ai_mode]
    page_size = 25


# ─── Message Admin (read-only) ────────────────────────────────────────────────

class MessageAdmin(ModelView, model=Message):
    name = "Message"
    name_plural = "Messages"
    icon = "fa-solid fa-message"

    column_list = [
        Message.id,
        Message.role,
        Message.content,
        Message.tenant_id,
        Message.conversation_id,
        Message.created_at,
    ]
    column_searchable_list = [Message.content]
    column_sortable_list = [Message.role, Message.created_at]
    column_filters = [Message.role]

    can_create = False
    can_edit = False
    can_delete = True   # allow cleanup only
    can_view_details = True
    can_export = True

    page_size = 50


# ─── All views to register ────────────────────────────────────────────────────
ALL_ADMIN_VIEWS = [
    TenantAdmin,
    UserAdmin,
    DocumentAdmin,
    ConversationAdmin,
    MessageAdmin,
]
