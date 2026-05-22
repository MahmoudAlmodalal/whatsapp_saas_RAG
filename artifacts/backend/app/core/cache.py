import logging
import redis.asyncio as redis
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _make_redis_client():
    try:
        import socket
        url = settings.REDIS_URL
        host = url.split("://")[-1].split(":")[0].split("/")[0]
        port = int(url.split(":")[-1].split("/")[0]) if ":" in url.split("://")[-1] else 6379
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        client = redis.from_url(url, decode_responses=True)
        logger.info("Connected to Redis at %s", url)
        return client
    except Exception:
        logger.warning("Redis unavailable — falling back to fakeredis (in-memory)")
        import fakeredis.aioredis as fakeredis
        return fakeredis.FakeRedis(decode_responses=True)

redis_client = _make_redis_client()

async def get_tenant_id_by_phone(phone: str) -> str | None:
    return await redis_client.get(f"wa_tenant:{phone}")

async def set_tenant_phone_mapping(phone: str, tenant_id: str) -> None:
    await redis_client.set(f"wa_tenant:{phone}", tenant_id)
