from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.routers.health import router as health_router
from app.routers.chat import router as chat_router
from app.routers.upload import router as upload_router
from app.routers.analytics import router as analytics_router
from app.routers.handoff import router as handoff_router
from app.routers.learn import router as learn_router
from app.routers.settings import router as settings_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.whatsapp_webhook import router as whatsapp_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_tables()
    print(f"🚀  Naseh AI backend started [{settings.ENVIRONMENT}]")
    yield
    print("🛑  Naseh AI backend shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Naseh AI — نصيح",
        description="AI Customer Support Agent — RAG-powered, bilingual, multi-channel",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(upload_router)
    app.include_router(analytics_router)
    app.include_router(handoff_router)
    app.include_router(learn_router)
    app.include_router(settings_router)
    app.include_router(telegram_router)
    app.include_router(whatsapp_router)

    return app


app = create_app()
