from app.config import Settings


def test_settings_accepts_release_debug_flag():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@postgres:5432/db",
        REDIS_URL="redis://redis:6379/0",
        SECRET_KEY="test-secret",
        DEBUG="release",
    )

    assert settings.DEBUG is False
