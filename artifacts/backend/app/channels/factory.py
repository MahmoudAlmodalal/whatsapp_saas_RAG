from app.channels.base import BaseChannel

class ChannelFactory:
    _registry: dict = {}

    @classmethod
    def create(cls, channel_type: str) -> BaseChannel:
        if channel_type not in cls._registry:
            cls._lazy_register()
        if channel_type not in cls._registry:
            raise ValueError(f"Unknown channel: {channel_type}")
        return cls._registry[channel_type]()

    @classmethod
    def _lazy_register(cls):
        if cls._registry:
            return
        from app.channels.telegram_channel import TelegramChannel
        from app.channels.whatsapp_channel import WhatsAppChannel
        from app.channels.web_channel import WebChannel
        cls._registry = {
            "telegram": TelegramChannel,
            "whatsapp": WhatsAppChannel,
            "web": WebChannel,
        }

    @classmethod
    def register(cls, name: str, channel_class):
        cls._registry[name] = channel_class
