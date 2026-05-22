from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.schemas import CompanySettings

router = APIRouter()

class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    persona_name: Optional[str] = None
    tone: Optional[str] = None
    language_preference: Optional[str] = None
    system_prompt_extra: Optional[str] = None
    telegram_token: Optional[str] = None

@router.get("/api/v1/settings")
async def get_settings_endpoint(company_id: str = "default"):
    db = next(get_db())
    try:
        s = db.query(CompanySettings).filter(CompanySettings.id == company_id).first()
        if not s:
            s = CompanySettings(id=company_id)
            db.add(s)
            db.commit()
        return {
            "company_name": s.company_name,
            "persona_name": s.persona_name,
            "tone": s.tone,
            "language_preference": s.language_preference,
            "system_prompt_extra": s.system_prompt_extra or "",
            "telegram_token": s.telegram_token or "",
        }
    finally:
        db.close()

@router.put("/api/v1/settings")
async def update_settings(req: SettingsUpdate, company_id: str = "default"):
    db = next(get_db())
    try:
        s = db.query(CompanySettings).filter(CompanySettings.id == company_id).first()
        if not s:
            s = CompanySettings(id=company_id)
            db.add(s)
        if req.company_name is not None:
            s.company_name = req.company_name
        if req.persona_name is not None:
            s.persona_name = req.persona_name
        if req.tone is not None:
            s.tone = req.tone
        if req.language_preference is not None:
            s.language_preference = req.language_preference
        if req.system_prompt_extra is not None:
            s.system_prompt_extra = req.system_prompt_extra
        if req.telegram_token is not None:
            s.telegram_token = req.telegram_token
        db.commit()
        return {"success": True, "message": "تم حفظ الإعدادات بنجاح."}
    finally:
        db.close()
