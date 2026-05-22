from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.tenants import SubscriptionTier

class TenantConfigUpdate(BaseModel):
    ai_persona_name: str | None = Field(None, description="Name of the AI persona")
    language: str | None = Field(None, description="Primary language for the tenant")
    tone: str | None = Field(None, description="Tone of the AI")
    handoff_keywords: list[str] | None = Field(None, description="Keywords that trigger human handoff")
    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0, description="Confidence threshold for AI responses")
    max_context_turns: int | None = Field(None, ge=1, description="Maximum number of context turns to remember")
    whatsapp_token: str | None = Field(None, description="WhatsApp Business API access token")
    whatsapp_phone_number_id: str | None = Field(None, description="WhatsApp Business Phone Number ID")
    whatsapp_verify_token: str | None = Field(None, description="WhatsApp Webhook verify token")
    whatsapp_app_secret: str | None = Field(None, description="WhatsApp App Secret for signature validation")

class TenantCreate(BaseModel):
    name: str = Field(..., max_length=255, description="Display name of the business / tenant")
    whatsapp_number: str | None = Field(None, max_length=20, description="E.164 WhatsApp Business number")
    subscription_tier: SubscriptionTier = Field(
        SubscriptionTier.basic,
        description="Billing tier controlling feature access",
    )

class TenantResponse(BaseModel):
    id: UUID
    name: str
    whatsapp_number: str | None
    subscription_tier: SubscriptionTier
    config: dict[str, Any]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
