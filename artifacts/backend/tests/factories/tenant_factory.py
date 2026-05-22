"""
tests/factories/tenant_factory.py
──────────────────────────────────
TenantFactory — generates realistic multi-tenant test data using factory_boy + Faker.

Supports Arabic locale for authentic test data matching the Arabic-first system design.
"""
import uuid
import factory
from faker import Faker

from app.models.tenants import Tenant, SubscriptionTier

# Arabic locale faker for realistic business names
_ar_fake = Faker("ar_AA")
_en_fake = Faker("en_US")


class TenantFactory(factory.Factory):
    """Factory for generating Tenant instances."""

    class Meta:
        model = Tenant

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.LazyFunction(
        lambda: _ar_fake.company() or f"مؤسسة {_ar_fake.last_name()} التجارية"
    )
    whatsapp_number = factory.Sequence(
        lambda n: f"+9665{str(n).zfill(8)}"  # Saudi numbers: +966 5XXXXXXXX
    )
    subscription_tier = factory.Iterator(
        [SubscriptionTier.basic, SubscriptionTier.pro, SubscriptionTier.enterprise]
    )
    is_active = True
    config = factory.LazyFunction(
        lambda: {
            "ai_persona_name": "مساعد ذكي",
            "language": "arabic",
            "tone": "friendly",
            "handoff_keywords": ["تكلم مع موظف", "إنسان", "مشرف", "خدمة عملاء"],
            "confidence_threshold": 0.5,
            "max_context_turns": 5,
            "business_hours": "9AM-9PM",
        }
    )

    class Params:
        """Additional parameter variants."""

        # Usage: TenantFactory.build(pro=True)
        pro = factory.Trait(subscription_tier=SubscriptionTier.pro)
        enterprise = factory.Trait(subscription_tier=SubscriptionTier.enterprise)
        inactive = factory.Trait(is_active=False)

        # Tenant with handoff disabled
        no_handoff = factory.Trait(
            config=factory.LazyFunction(
                lambda: {
                    "ai_persona_name": "مساعد ذكي",
                    "language": "arabic",
                    "tone": "professional",
                    "handoff_keywords": [],
                    "confidence_threshold": 0.7,
                    "max_context_turns": 10,
                }
            )
        )
