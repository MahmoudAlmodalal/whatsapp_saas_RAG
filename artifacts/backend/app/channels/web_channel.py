from app.channels.base import BaseChannel

class WebChannel(BaseChannel):
    async def send(self, recipient_id: str, message: str) -> bool:
        return True

    async def receive(self, raw_payload: dict) -> dict:
        return {
            "sender_id": raw_payload.get("session_id", "web_user"),
            "message": raw_payload.get("message", ""),
            "session_id": raw_payload.get("session_id", "web_default"),
        }
