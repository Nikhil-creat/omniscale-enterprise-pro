# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root_shows_branding(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["designed_and_developed_by"] == "NIKHIL CHARY SRIRAMOJU"


@pytest.mark.asyncio
async def test_register_and_login(client):
    payload = {"email": "test.user@omniscale.dev", "password": "supersecret123", "full_name": "Test User"}
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    assert resp.json()["email"] == payload["email"]

    # Duplicate registration is rejected
    dup = await client.post("/api/v1/auth/register", json=payload)
    assert dup.status_code == 409

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == payload["email"]


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    payload = {"email": "wrongpass@omniscale.dev", "password": "correcthorsebattery"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": "not-the-password"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_lifecycle(client):
    payload = {"email": "apikey.user@omniscale.dev", "password": "supersecret123"}
    await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/api/v1/auth/api-keys", json={"name": "ci-key"}, headers=headers)
    assert created.status_code == 201
    key_data = created.json()
    assert key_data["plaintext_key"].startswith("osk_")

    listed = await client.get("/api/v1/auth/api-keys", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    revoked = await client.delete(f"/api/v1/auth/api-keys/{key_data['id']}", headers=headers)
    assert revoked.status_code == 204
