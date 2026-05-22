from abc import ABC, abstractmethod

class BaseChannel(ABC):
    @abstractmethod
    async def send(self, recipient_id: str, message: str) -> bool:
        pass

    @abstractmethod
    async def receive(self, raw_payload: dict) -> dict:
        """Returns: { "sender_id": str, "message": str, "session_id": str }"""
        pass
