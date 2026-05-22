"""
app/services/subscription.py
──────────────────────────────
Subscription quota enforcement for the inbound message pipeline.

How it works
────────────
  Async side (webhook handler):
    • After resolving tenant_id, the webhook caches the tenant's subscription
      tier in Redis under ``sub:tier:{tenant_id}`` (TTL = 1 h).
    • Use ``cache_tenant_tier(tenant_id, tier, redis)`` for this.

  Sync side (Celery task):
    • ``check_and_increment(tenant_id, redis_sync)`` reads the cached tier,
      checks the monthly quota, and atomically increments the counter if
      there is remaining capacity.
    • The monthly counter lives at ``sub:usage:{tenant_id}:{YYYY-MM}`` and
      auto-expires after ~35 days so stale keys never accumulate.
    • Returns a ``QuotaResult`` dataclass so callers know whether to proceed,
      and what usage numbers to log / surface to the tenant.

Plan limits
───────────
  basic      →   50 messages / month   (Free plan)
  pro        → 2 000 messages / month  (Pro plan)
  enterprise →  None (unlimited)

  Unmapped / unknown tiers fall back to the ``basic`` limit as a safe default.

Redis key schema
────────────────
  sub:tier:{tenant_id}               → tier string, TTL 3 600 s
  sub:usage:{tenant_id}:{YYYY-MM}    → integer counter, TTL 35 days
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Quota table ───────────────────────────────────────────────────────────────
# Map every known SubscriptionTier value → monthly message limit.
# None means unlimited.
PLAN_LIMITS: dict[str, Optional[int]] = {
    # Python / SQLAlchemy tier enum values
    "basic":      50,
    "pro":        2_000,
    "enterprise": None,
    # Drizzle / dashboard label variants (belt-and-braces)
    "free":       50,
    "starter":    500,
    "business":   None,
}

_DEFAULT_LIMIT = 50          # applied when tier is missing / unrecognised
_TIER_TTL = 3_600            # 1 hour — how long to cache the tier in Redis
_USAGE_TTL = 35 * 86_400     # 35 days — counter auto-expires well past month end


# ── Redis key helpers ─────────────────────────────────────────────────────────

def _tier_key(tenant_id: str) -> str:
    return f"sub:tier:{tenant_id}"


def _usage_key(tenant_id: str) -> str:
    """Monthly counter key, e.g. sub:usage:{tenant_id}:2026-05"""
    ym = datetime.now(tz=timezone.utc).strftime("%Y-%m")
    return f"sub:usage:{tenant_id}:{ym}"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QuotaResult:
    allowed: bool
    used: int         # value *after* increment (or current value if denied)
    limit: int | None # None = unlimited
    tier: str


# ── Async helpers (called from webhook handler) ───────────────────────────────

async def cache_tenant_tier(tenant_id: str, tier: str, redis_async) -> None:
    """
    Store the tenant's subscription tier in Redis so Celery workers can read
    it without hitting the database.

    Args:
        tenant_id:   Tenant UUID string.
        tier:        SubscriptionTier value, e.g. "basic", "pro", "enterprise".
        redis_async: An ``aioredis.Redis`` client with ``decode_responses=True``.
    """
    await redis_async.set(_tier_key(tenant_id), tier, ex=_TIER_TTL)
    logger.debug("Cached tier '%s' for tenant %s (TTL %ds)", tier, tenant_id, _TIER_TTL)


async def get_cached_tier(tenant_id: str, redis_async) -> str | None:
    """Return the cached tier string, or None on cache miss."""
    return await redis_async.get(_tier_key(tenant_id))


# ── Sync helper (called from Celery task) ────────────────────────────────────

def check_and_increment(tenant_id: str, redis_sync) -> QuotaResult:
    """
    Atomically check the monthly quota and increment the counter if allowed.

    Uses a Redis INCR pipeline so the read-then-write is race-free even with
    multiple Celery worker processes running in parallel.

    Algorithm:
      1. Read cached tier → derive limit.
      2. INCR the monthly counter (atomic).
      3. On the first increment (value == 1), set the 35-day TTL.
      4. If the new value exceeds the limit, decrement back and return denied.
         (Decrement keeps the counter accurate; the task is dropped, not retried.)

    Args:
        tenant_id:   Tenant UUID string.
        redis_sync:  A synchronous ``redis.Redis`` client with
                     ``decode_responses=True``.

    Returns:
        QuotaResult with ``allowed=True`` if the message may proceed.
    """
    # ── 1. Resolve plan limit from cached tier ────────────────────────────────
    tier_raw: str | None = redis_sync.get(_tier_key(tenant_id))
    tier = (tier_raw or "basic").lower().strip()
    limit = PLAN_LIMITS.get(tier, _DEFAULT_LIMIT)

    # Unlimited plans bypass all counter logic
    if limit is None:
        logger.debug(
            "Quota check skipped (unlimited) — tenant=%s tier=%s", tenant_id, tier
        )
        return QuotaResult(allowed=True, used=0, limit=None, tier=tier)

    # ── 2. Atomic INCR ────────────────────────────────────────────────────────
    key = _usage_key(tenant_id)
    new_value: int = redis_sync.incr(key)

    # On first write, set the expiry (INCR creates the key if absent)
    if new_value == 1:
        redis_sync.expire(key, _USAGE_TTL)
        logger.debug(
            "Usage counter created — tenant=%s key=%s TTL=%ds",
            tenant_id, key, _USAGE_TTL,
        )

    # ── 3. Enforce limit ──────────────────────────────────────────────────────
    if new_value > limit:
        # Roll back the increment so the counter stays accurate
        redis_sync.decr(key)
        logger.warning(
            "Quota exceeded — tenant=%s tier=%s used=%d limit=%d",
            tenant_id, tier, new_value - 1, limit,
        )
        return QuotaResult(allowed=False, used=new_value - 1, limit=limit, tier=tier)

    logger.info(
        "Quota check passed — tenant=%s tier=%s used=%d/%d",
        tenant_id, tier, new_value, limit,
    )
    return QuotaResult(allowed=True, used=new_value, limit=limit, tier=tier)


def get_current_usage(tenant_id: str, redis_sync) -> int:
    """
    Return the current monthly usage count for a tenant (read-only).
    Returns 0 if no counter exists yet.
    """
    value = redis_sync.get(_usage_key(tenant_id))
    return int(value) if value else 0
