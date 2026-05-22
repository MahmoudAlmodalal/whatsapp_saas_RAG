"""
tests/factories/user_factory.py
────────────────────────────────
UserFactory — generates test User instances across all roles.

All passwords default to 'test_password_123' (pre-hashed).
"""
import uuid
import factory
from faker import Faker

from app.models.user import User, UserRole
from app.core.security import hash_password

_en_fake = Faker("en_US")

# Pre-hash a common test password once at import time to avoid bcrypt overhead
_HASHED_TEST_PASSWORD = hash_password("test_password_123")


class UserFactory(factory.Factory):
    """Factory for generating User instances."""

    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)   # override with real tenant.id in tests
    email = factory.Sequence(lambda n: f"user_{n}@test.sa")
    hashed_password = _HASHED_TEST_PASSWORD
    role = UserRole.agent
    is_active = True

    class Params:
        """Role variants."""

        admin = factory.Trait(
            role=UserRole.admin,
            email=factory.Sequence(lambda n: f"admin_{n}@test.sa"),
        )
        agent = factory.Trait(
            role=UserRole.agent,
            email=factory.Sequence(lambda n: f"agent_{n}@test.sa"),
        )
        operator = factory.Trait(
            role=UserRole.operator,
            email=factory.Sequence(lambda n: f"operator_{n}@test.sa"),
        )
        inactive = factory.Trait(is_active=False)
