#!/usr/bin/env python
"""
scripts/create_super_admin.py
───────────────────────────────
CLI script to create a platform-level super_admin user.

Super admins:
  - Can log into /admin panel
  - Can manage ALL tenants across the platform
  - Are NOT scoped to any single tenant (tenant_id = null)

Usage:
    # Inside Docker (recommended):
    docker-compose exec app python scripts/create_super_admin.py \\
        --email superadmin@platform.sa \\
        --password "StrongPass123!"

    # Locally:
    python scripts/create_super_admin.py --email admin@me.sa --password Pass123!
"""
import asyncio
import argparse
import sys
import uuid
import os

os.environ.setdefault("ENVIRONMENT", "production")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.tenants import Tenant, SubscriptionTier
from app.models.user import User, UserRole
from app.core.security import hash_password

# Platform sentinel tenant — super_admin lives in this special tenant
PLATFORM_TENANT_NAME = "⚙️ Platform (Super Admin)"


async def get_or_create_platform_tenant(session: AsyncSession) -> Tenant:
    """Get or create the special platform tenant for super_admin users."""
    result = await session.execute(
        select(Tenant).where(Tenant.name == PLATFORM_TENANT_NAME)
    )
    tenant = result.scalar_one_or_none()
    if tenant:
        return tenant

    tenant = Tenant(
        name=PLATFORM_TENANT_NAME,
        whatsapp_number=None,
        subscription_tier=SubscriptionTier.enterprise,
        config={
            "ai_persona_name": "Platform Admin",
            "language": "arabic",
            "tone": "professional",
            "handoff_keywords": [],
            "confidence_threshold": 1.0,
            "max_context_turns": 0,
            "_platform_tenant": True,  # marker flag
        },
    )
    session.add(tenant)
    await session.flush()
    print(f"  ✅ Created platform tenant (id={tenant.id})")
    return tenant


async def create_super_admin(email: str, password: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        # Check email not taken
        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"❌  User '{email}' already exists.")
            sys.exit(1)

        # Get/create platform tenant
        platform_tenant = await get_or_create_platform_tenant(session)

        # Create super_admin user
        user = User(
            tenant_id=platform_tenant.id,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.super_admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()

        print("\n" + "═" * 55)
        print("✅  Super Admin created successfully!")
        print("═" * 55)
        print(f"  Email     : {user.email}")
        print(f"  Role      : {user.role.value}")
        print(f"  User ID   : {user.id}")
        print(f"  Tenant    : {platform_tenant.name}")
        print(f"  Tenant ID : {platform_tenant.id}")
        print("═" * 55)
        print(f"\n  🌐  Admin panel: http://localhost:8000/admin")
        print(f"  🔑  Login with: {email}\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Create a platform super_admin user for the /admin panel."
    )
    parser.add_argument("--email", required=True, help="Super admin email address")
    parser.add_argument("--password", required=True, help="Password (min 8 chars)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌  Password must be at least 8 characters.")
        sys.exit(1)

    asyncio.run(create_super_admin(email=args.email, password=args.password))


if __name__ == "__main__":
    main()
