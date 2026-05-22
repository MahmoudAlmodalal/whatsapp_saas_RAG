from app.channels.base import BaseChannel
from app.config import get_settings

settings = get_settings()

class WhatsAppChannel(BaseChannel):
    def __init__(self):
        self.sid = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER

    async def send(self, recipient_id: str, message: str) -> bool:
        if not self.sid or not self.token:
            return False
        try:
            from twilio.rest import Client
            client = Client(self.sid, self.token)
            client.messages.create(
                body=message,
                from_=self.from_number,
                to=f"whatsapp:{recipient_id}",
            )
            return True
        except Exception:
            return False

    async def receive(self, raw_payload: dict) -> dict:
        sender = raw_payload.get("From", "").replace("whatsapp:", "")
        return {
            "sender_id": sender,
            "message": raw_payload.get("Body", ""),
            "session_id": f"whatsapp_{sender}",
        }
