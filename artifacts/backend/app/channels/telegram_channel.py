import os
import httpx
from app.channels.base import BaseChannel
from app.config import get_settings

settings = get_settings()

class TelegramChannel(BaseChannel):
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN

    async def send(self, recipient_id: str, message: str) -> bool:
        if not self.token:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"chat_id": recipient_id, "text": message})
        return r.status_code == 200

    async def receive(self, raw_payload: dict) -> dict:
        msg = raw_payload.get("message", {})
        sender = str(msg.get("from", {}).get("id", ""))
        return {
            "sender_id": sender,
            "message": msg.get("text", ""),
            "session_id": f"telegram_{sender}",
        }
