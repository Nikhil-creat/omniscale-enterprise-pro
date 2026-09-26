# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
from unittest.mock import AsyncMock, patch

import pytest


async def _register_and_login(client, email: str) -> dict:
    payload = {"email": email, "password": "supersecret123"}
    await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_agent_invoke_routes_to_chat(client):
    headers = await _register_and_login(client, "agent.user@omniscale.dev")

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 1
    fake_redis.expire.return_value = True

    with patch("backend.rate_limit.get_redis", return_value=fake_redis), \
         patch("backend.agent.get_llm_client") as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_client.complete.side_effect = ["chat", "Hello! This is a test response."]
        mock_client.provider.value = "groq"

        resp = await client.post(
            "/api/v1/agent/invoke", json={"prompt": "Hello there"}, headers=headers
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["route_taken"] == "chat"
    assert body["answer"] == "Hello! This is a test response."


@pytest.mark.asyncio
async def test_agent_invoke_requires_auth(client):
    resp = await client.post("/api/v1/agent/invoke", json={"prompt": "Hello"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rag_document_upload_dispatches_celery_task(client):
    headers = await _register_and_login(client, "rag.user@omniscale.dev")

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 1
    fake_redis.expire.return_value = True

    fake_async_result = type("R", (), {"id": "celery-task-123"})()

    with patch("backend.rate_limit.get_redis", return_value=fake_redis), \
         patch("backend.routers.rag_router.run_rag_ingest.delay", return_value=fake_async_result):
        files = {"file": ("notes.txt", b"OmniScale is a multi-tenant AI SaaS platform.", "text/plain")}
        resp = await client.post("/api/v1/rag/documents", files=files, headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["celery_task_id"] == "celery-task-123"


@pytest.mark.asyncio
async def test_cnn_analyze_dispatches_celery_task(client):
    headers = await _register_and_login(client, "cnn.user@omniscale.dev")

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 1
    fake_redis.expire.return_value = True

    fake_async_result = type("R", (), {"id": "celery-cnn-456"})()

    with patch("backend.rate_limit.get_redis", return_value=fake_redis), \
         patch("backend.routers.cnn_router.run_cnn_inference.delay", return_value=fake_async_result):
        files = {"file": ("image.png", b"\x89PNG\r\n\x1a\nfake-bytes", "image/png")}
        resp = await client.post("/api/v1/cnn/analyze", files=files, headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_type"] == "cnn"
    assert body["celery_task_id"] == "celery-cnn-456"


@pytest.mark.asyncio
async def test_rate_limit_enforced(client):
    headers = await _register_and_login(client, "ratelimit.user@omniscale.dev")

    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 999  # already far over any tier's limit
    fake_redis.expire.return_value = True
    fake_redis.ttl.return_value = 42

    with patch("backend.rate_limit.get_redis", return_value=fake_redis), \
         patch("backend.agent.get_llm_client") as mock_client_factory:
        mock_client_factory.return_value.complete.return_value = "chat"
        resp = await client.post(
            "/api/v1/agent/invoke", json={"prompt": "test"}, headers=headers
        )

    assert resp.status_code == 429
