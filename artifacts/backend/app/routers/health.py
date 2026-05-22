from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "service": "naseh"}

@router.get("/ready")
async def ready():
    return {"status": "ready"}
