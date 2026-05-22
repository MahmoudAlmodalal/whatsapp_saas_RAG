#!/usr/bin/env python
"""
scripts/create_admin.py
────────────────────────
CLI script to create an admin user for an existing tenant.

Usage:
    python scripts/create_admin.py \
        --email admin@mybusiness.sa \
        --password MySecurePass123 \
        --tenant-id <UUID>          # optional: creates a tenant if omitted

Run inside Docker:
    docker-compose exec app python scripts/create_admin.py --email ... --password ...
"""
import asyncio
import argparse
import sys
import uuid
import os

# Must be set before importing app modules
os.environ.setdefault("ENVIRONMENT", "production")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.tenants import Tenant, SubscriptionTier
from app.models.user import User, UserRole
from app.core.security import hash_password


async def create_admin(
    email: str,
    password: str,
    tenant_id: str | None,
    tenant_name: str | None,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        # ── Resolve tenant ────────────────────────────────────────────────────
        if tenant_id:
            result = await session.execute(
                select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                print(f"❌ Tenant with id={tenant_id} not found.")
                sys.exit(1)
        else:
            # Create a new tenant
            name = tenant_name or f"Tenant for {email}"
            tenant = Tenant(
                name=name,
                subscription_tier=SubscriptionTier.pro,
                config={
                    "ai_persona_name": "مساعد ذكي",
                    "language": "arabic",
                    "tone": "professional",
                    "handoff_keywords": ["تكلم مع موظف", "إنسان"],
                    "confidence_threshold": 0.5,
                    "max_context_turns": 10,
                },
            )
            session.add(tenant)
            await session.flush()
            print(f"✅ Created new tenant: {tenant.name} (id={tenant.id})")

        # ── Check if email already exists ─────────────────────────────────────
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"❌ User with email '{email}' already exists.")
            sys.exit(1)

        # ── Create admin user ─────────────────────────────────────────────────
        user = User(
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()

        print("\n" + "═" * 50)
        print("✅  Admin user created successfully!")
        print("═" * 50)
        print(f"  Email     : {user.email}")
        print(f"  Role      : {user.role.value}")
        print(f"  Tenant ID : {tenant.id}")
        print(f"  Tenant    : {tenant.name}")
        print(f"  User ID   : {user.id}")
        print("═" * 50 + "\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Create an admin user for a tenant.")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--password", required=True, help="Admin user password (min 8 chars)")
    parser.add_argument("--tenant-id", default=None, help="Existing tenant UUID (optional)")
    parser.add_argument("--tenant-name", default=None, help="New tenant name if creating one")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ Password must be at least 8 characters.")
        sys.exit(1)

    asyncio.run(create_admin(
        email=args.email,
        password=args.password,
        tenant_id=args.tenant_id,
        tenant_name=args.tenant_name,
    ))


if __name__ == "__main__":
    main()
