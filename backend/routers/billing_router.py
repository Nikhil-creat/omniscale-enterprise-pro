"""
backend/routers/billing_router.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.billing import BillingError, create_checkout_session, handle_webhook_event, verify_webhook_signature
from backend.database import get_db
from backend.models import Document, InferenceJob, Subscription, User
from backend.rate_limit import _TIER_LIMITS, get_redis
from backend.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionOut,
    UsageMetrics,
    WebhookAck,
)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
logger = logging.getLogger("omniscale.billing_router")


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def checkout(
    payload: CheckoutSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    try:
        result = await create_checkout_session(db, user, payload.tier)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CheckoutSessionResponse(**result)


@router.post("/webhook", response_model=WebhookAck)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> WebhookAck:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = verify_webhook_signature(payload, sig_header)
    except BillingError as exc:
        logger.warning("Rejected Stripe webhook: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await handle_webhook_event(db, event)
    return WebhookAck(event_type=event["type"], detail=result)


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription record found")
    return sub


@router.get("/usage", response_model=UsageMetrics)
async def get_usage(
    request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UsageMetrics:
    sub = user.subscription
    tier = sub.tier if sub and sub.status.value == "active" else "free"
    limit = _TIER_LIMITS.get(sub.tier, 20) if sub else 20

    r = get_redis()
    key = f"ratelimit:{user.id}:/api/v1/agent/invoke"
    current = await r.get(key)

    doc_count = await db.scalar(select(func.count(Document.id)).where(Document.user_id == user.id))
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    job_count = await db.scalar(
        select(func.count(InferenceJob.id)).where(
            InferenceJob.user_id == user.id, InferenceJob.created_at >= since
        )
    )

    return UsageMetrics(
        tier=str(tier.value if hasattr(tier, "value") else tier),
        requests_this_minute=int(current or 0),
        requests_limit_per_minute=limit,
        documents_indexed=doc_count or 0,
        jobs_last_24h=job_count or 0,
    )
