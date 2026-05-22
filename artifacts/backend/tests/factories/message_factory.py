"""
tests/factories/message_factory.py
────────────────────────────────────
MessageFactory — generates test Message instances with realistic Arabic content.
"""
import uuid
import random
from datetime import datetime, timezone
import factory

from app.models.messages import Message, MessageRole

_ARABIC_CUSTOMER_MESSAGES = [
    "ما هي ساعات العمل لديكم؟",
    "كيف يمكنني إرجاع المنتج؟",
    "هل يتوفر منتج باللون الأحمر؟",
    "أريد حجز موعد",
    "ما هو سعر الشحن إلى الرياض؟",
    "هل تقبلون الدفع بالبطاقة الائتمانية؟",
    "متى يصل الطلب؟",
    "أحتاج مساعدة في طلبيتي",
    "هل يمكنني تغيير عنوان التوصيل؟",
    "شكراً لكم على الخدمة",
]

_ARABIC_ASSISTANT_MESSAGES = [
    "أهلاً بك! يسعدني مساعدتك.",
    "ساعات العمل من 9 صباحاً حتى 9 مساءً.",
    "يمكنك إرجاع المنتج خلال 14 يوماً من تاريخ الشراء.",
    "نعم، المنتج متاح بثلاثة ألوان: أحمر، أزرق، وأخضر.",
    "سعر الشحن هو 30 ريالاً للطلبات دون 200 ريال.",
    "نعم، نقبل جميع بطاقات الائتمان والدفع الإلكتروني.",
    "سيصل طلبك خلال 3-5 أيام عمل.",
    "يمكنني مساعدتك في طلبيتك بالتأكيد.",
    "نعم، يمكنك تغيير عنوان التوصيل قبل الشحن.",
    "شكراً لك! يسعدنا خدمتك دائماً.",
]


class MessageFactory(factory.Factory):
    """Factory for generating Message instances."""

    class Meta:
        model = Message

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)
    conversation_id = factory.LazyFunction(uuid.uuid4)
    role = MessageRole.customer
    content = factory.LazyFunction(lambda: random.choice(_ARABIC_CUSTOMER_MESSAGES))
    created_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    meta_data = factory.LazyFunction(lambda: {"whatsapp_message_id": f"wamid.{uuid.uuid4().hex}"})

    class Params:
        """Role variants."""

        customer = factory.Trait(
            role=MessageRole.customer,
            content=factory.LazyFunction(
                lambda: random.choice(_ARABIC_CUSTOMER_MESSAGES)
            ),
        )
        assistant = factory.Trait(
            role=MessageRole.assistant,
            content=factory.LazyFunction(
                lambda: random.choice(_ARABIC_ASSISTANT_MESSAGES)
            ),
        )
