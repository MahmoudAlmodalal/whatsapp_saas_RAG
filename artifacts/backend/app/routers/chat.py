from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from app.core.agent import process_message
from app.database import get_db
from app.models.schemas import CompanySettings

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    company_id: str = "default"
    channel: str = "web"

def _get_company_settings(company_id: str) -> CompanySettings:
    db = next(get_db())
    try:
        settings = db.query(CompanySettings).filter(CompanySettings.id == company_id).first()
        if not settings:
            settings = CompanySettings(id=company_id)
        return settings
    finally:
        db.close()

@router.post("/api/v1/chat")
async def chat(req: ChatRequest):
    cs = _get_company_settings(req.company_id)
    result = await process_message(
        message=req.message,
        session_id=req.session_id,
        company_id=req.company_id,
        channel=req.channel,
        persona_name=cs.persona_name or "نصيح",
        tone=cs.tone or "professional",
        system_prompt_extra=cs.system_prompt_extra or "",
    )
    return result

@router.websocket("/api/v1/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    company_id = "default"
    cs = _get_company_settings(company_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message.strip():
                continue
            result = await process_message(
                message=message,
                session_id=session_id,
                company_id=company_id,
                channel="web",
                persona_name=cs.persona_name or "نصيح",
                tone=cs.tone or "professional",
                system_prompt_extra=cs.system_prompt_extra or "",
            )
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
