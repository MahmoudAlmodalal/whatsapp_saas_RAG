from fastapi import APIRouter, Request
from app.channels.whatsapp_channel import WhatsAppChannel
from app.core.agent import process_message

router = APIRouter()
_channel = WhatsAppChannel()

@router.post("/api/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    payload = dict(form_data)
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
            channel="whatsapp",
        )
        await _channel.send(data["sender_id"], result["answer"])
    except Exception:
        pass
    return {"ok": True}
