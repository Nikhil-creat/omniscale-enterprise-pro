# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
from unittest.mock import MagicMock, patch

import pytest
import stripe

from backend.billing import BillingError, verify_webhook_signature


def test_webhook_rejects_bad_signature():
    with pytest.raises(BillingError):
        verify_webhook_signature(b'{"type": "checkout.session.completed"}', "bad-signature")


@pytest.mark.asyncio
async def test_stripe_webhook_endpoint_rejects_missing_signature(client):
    resp = await client.post("/api/v1/billing/webhook", content=b"{}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    resp = await client.post("/api/v1/billing/checkout", json={"tier": "pro"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_checkout_session_created_for_authenticated_user(client, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_test_123")

    payload = {"email": "billing.user@omniscale.dev", "password": "supersecret123"}
    await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fake_customer = {"id": "cus_test_123"}
    fake_session = {"url": "https://checkout.stripe.com/pay/cs_test_123", "id": "cs_test_123"}

    with patch("backend.billing.stripe.Customer.create", return_value=fake_customer), \
         patch("backend.billing.stripe.checkout.Session.create", return_value=fake_session), \
         patch("backend.billing._TIER_PRICE_MAP", {"pro": "price_test_123", "enterprise": "price_test_456"}):
        resp = await client.post("/api/v1/billing/checkout", json={"tier": "pro"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "cs_test_123"
    assert body["checkout_url"].startswith("https://checkout.stripe.com")


@pytest.mark.asyncio
async def test_checkout_rejects_unconfigured_tier(client):
    payload = {"email": "notier.user@omniscale.dev", "password": "supersecret123"}
    await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    with patch("backend.billing._TIER_PRICE_MAP", {"pro": None, "enterprise": None}):
        resp = await client.post("/api/v1/billing/checkout", json={"tier": "pro"}, headers=headers)
    assert resp.status_code == 400
