"""
app/models/user.py
──────────────────
User model — platform users belonging to a tenant.

Roles
-----
- super_admin : platform-level — can manage ALL tenants (not RLS-scoped)
- admin       : full control over their own tenant's resources
- agent       : can read/write conversations, cannot change config
- operator    : read-only analytics / monitoring

Super admins have `tenant_id` set to a special platform tenant (UUID nil)
and bypass all RLS policies in the admin panel.
"""
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    super_admin = "super_admin"  # Platform-level: can manage all tenants
    admin = "admin"              # Tenant-level: full control of own tenant
    agent = "agent"              # Tenant-level: conversation management
    operator = "operator"        # Tenant-level: read-only monitoring


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique user identifier (UUIDv4).",
    )

    # ── Multi-tenancy ─────────────────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK → tenants.id — scopes this user to a single tenant.",
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique login email (case-sensitive).",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt-hashed password — never store plaintext.",
    )

    # ── Role / permissions ────────────────────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"),
        nullable=False,
        default=UserRole.agent,
        server_default="agent",
        comment="RBAC role controlling route-level access.",
    )

    # ── Soft-disable ──────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Set False to lock the account without deleting the row.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp when the user was created.",
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="UTC timestamp of the last profile update.",
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")  # noqa: F821

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role} tenant={self.tenant_id}>"
