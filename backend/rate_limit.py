"""
backend/rate_limit.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Redis-backed fixed-window rate limiter, tiered by subscription plan.
Implemented with a single atomic INCR + EXPIRE so it is safe under
concurrent multi-worker load.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from backend.config import get_settings
from backend.models import SubscriptionTier, User

settings = get_settings()
_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


_TIER_LIMITS = {
    SubscriptionTier.FREE: settings.RATE_LIMIT_FREE_PER_MIN,
    SubscriptionTier.PRO: settings.RATE_LIMIT_PRO_PER_MIN,
    SubscriptionTier.ENTERPRISE: settings.RATE_LIMIT_ENTERPRISE_PER_MIN,
}


async def enforce_rate_limit(request: Request, user: User) -> None:
    tier = SubscriptionTier.FREE
    if user.subscription and user.subscription.status.value == "active":
        tier = user.subscription.tier

    limit = _TIER_LIMITS.get(tier, settings.RATE_LIMIT_FREE_PER_MIN)
    r = get_redis()
    key = f"ratelimit:{user.id}:{request.url.path}"
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, 60)
    if current > limit:
        ttl = await r.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit}/min for {tier.value} tier). Retry in {ttl}s.",
        )
