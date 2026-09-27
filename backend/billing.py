"""
backend/billing.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Stripe billing engine: Checkout Session creation for recurring subscription
tiers, signature-verified webhook handling for `checkout.session.completed`
and `invoice.paid` (plus cancellation/failure events), and an audit log of
every financial event.

Note on payouts: Stripe automatically transfers your available balance to
your connected bank account on the payout schedule configured in your
Stripe Dashboard — a standard SaaS charging its own customers should NOT
call the Payouts API directly. The Payouts API is for Stripe Connect
platforms that hold and then disburse *other people's* funds (e.g. a
marketplace paying sellers). This module implements standard billing
correctly and exposes an optional, clearly-separated Connect payout helper
for platforms that genuinely need it (STRIPE_CONNECT_ENABLED=true).
"""
from __future__ import annotations

import logging
from typing import Optional

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import AuditLog, Subscription, SubscriptionStatus, SubscriptionTier, User

logger = logging.getLogger("omniscale.billing")
settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

_TIER_PRICE_MAP = {
    "pro": settings.STRIPE_PRICE_ID_PRO,
    "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE,
}


class BillingError(Exception):
    pass


async def _ensure_stripe_customer(db: AsyncSession, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(email=user.email, name=user.full_name or user.email)
    user.stripe_customer_id = customer["id"]
    await db.commit()
    return customer["id"]


async def create_checkout_session(db: AsyncSession, user: User, tier: str) -> dict:
    price_id = _TIER_PRICE_MAP.get(tier)
    if not price_id:
        raise BillingError(f"No Stripe price configured for tier '{tier}'")

    customer_id = await _ensure_stripe_customer(db, user)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=settings.FRONTEND_CANCEL_URL,
        metadata={"user_id": user.id, "tier": tier},
        allow_promotion_codes=True,
    )
    return {"checkout_url": session["url"], "session_id": session["id"]}


def verify_webhook_signature(payload: bytes, sig_header: str) -> stripe.Event:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingError("STRIPE_WEBHOOK_SECRET is not configured")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise BillingError(f"Invalid webhook signature: {exc}") from exc


async def _get_or_create_subscription(db: AsyncSession, user_id: str) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(user_id=user_id)
        db.add(sub)
        await db.flush()
    return sub


async def _log_event(db: AsyncSession, user_id: Optional[str], event: stripe.Event, amount_cents: Optional[int] = None, currency: Optional[str] = None) -> None:
    log = AuditLog(
        user_id=user_id,
        event_type=event["type"],
        stripe_event_id=event["id"],
        amount_cents=amount_cents,
        currency=currency,
        raw_payload=str(event.get("data", {})),
    )
    db.add(log)
    await db.commit()


async def handle_webhook_event(db: AsyncSession, event: stripe.Event) -> dict:
    """Idempotently apply a verified Stripe event to our local subscription state."""
    existing = await db.execute(select(AuditLog).where(AuditLog.stripe_event_id == event["id"]))
    if existing.scalar_one_or_none():
        logger.info("Duplicate Stripe event %s ignored", event["id"])
        return {"status": "duplicate_ignored"}

    event_type = event["type"]
    data_obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data_obj.get("metadata", {}).get("user_id")
        tier = data_obj.get("metadata", {}).get("tier", "pro")
        stripe_sub_id = data_obj.get("subscription")
        if user_id:
            sub = await _get_or_create_subscription(db, user_id)
            sub.tier = SubscriptionTier(tier)
            sub.status = SubscriptionStatus.ACTIVE
            sub.stripe_subscription_id = stripe_sub_id
            await db.commit()
        await _log_event(db, user_id, event, amount_cents=data_obj.get("amount_total"), currency=data_obj.get("currency"))

    elif event_type == "invoice.paid":
        stripe_sub_id = data_obj.get("subscription")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id))
        sub = result.scalar_one_or_none()
        user_id = sub.user_id if sub else None
        if sub:
            sub.status = SubscriptionStatus.ACTIVE
            period_end = data_obj.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
            if period_end:
                from datetime import datetime, timezone

                sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
            await db.commit()
        await _log_event(db, user_id, event, amount_cents=data_obj.get("amount_paid"), currency=data_obj.get("currency"))

    elif event_type in ("invoice.payment_failed",):
        stripe_sub_id = data_obj.get("subscription")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id))
        sub = result.scalar_one_or_none()
        user_id = sub.user_id if sub else None
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE
            await db.commit()
        await _log_event(db, user_id, event)

    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = data_obj.get("id")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id))
        sub = result.scalar_one_or_none()
        user_id = sub.user_id if sub else None
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.tier = SubscriptionTier.FREE
            await db.commit()
        await _log_event(db, user_id, event)

    else:
        await _log_event(db, None, event)

    return {"status": "processed", "event_type": event_type}


# ---------------------------------------------------------------------------
# Optional: Stripe Connect payouts — ONLY relevant if OmniScale itself holds
# funds on behalf of third parties (e.g. a marketplace/platform model).
# ---------------------------------------------------------------------------
def trigger_connect_payout(connected_account_id: str, amount_cents: int, currency: str = "usd") -> dict:
    if not settings.STRIPE_CONNECT_ENABLED:
        raise BillingError("Stripe Connect payouts are disabled (STRIPE_CONNECT_ENABLED=false)")
    payout = stripe.Payout.create(
        amount=amount_cents,
        currency=currency,
        stripe_account=connected_account_id,
    )
    return {"payout_id": payout["id"], "status": payout["status"]}
