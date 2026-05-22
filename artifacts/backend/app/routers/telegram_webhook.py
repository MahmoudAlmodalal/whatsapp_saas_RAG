from fastapi import APIRouter, Request
from app.channels.telegram_channel import TelegramChannel
from app.core.agent import process_message

router = APIRouter()
_channel = TelegramChannel()

@router.post("/api/v1/telegram/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    try:
        data = await _channel.receive(payload)
        session_id = data["session_id"]
        message = data["message"]
        if not message.strip():
            return {"ok": True}
        result = await process_message(
            message=message,
            session_id=session_id,
            company_id="default",
            channel="telegram",
        )
        await _channel.send(data["sender_id"], result["answer"])
    except Exception:
        pass
    return {"ok": True}
