import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Naseh AI"
    ENVIRONMENT: str = "development"

    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o"
    CONFIDENCE_THRESHOLD: float = 0.35
    MAX_CONTEXT_MESSAGES: int = 10

    CHROMA_PERSIST_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma"
    )
    DATABASE_URL: str = "sqlite:///" + os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "naseh.db"
    )

    TELEGRAM_BOT_TOKEN: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""

    SECRET_KEY: str = "naseh-dev-secret-change-in-production"
    DEFAULT_COMPANY_ID: str = "default"
    DEFAULT_PERSONA_NAME: str = "نصيح"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()
