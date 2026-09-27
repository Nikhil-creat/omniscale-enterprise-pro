"""
backend/tasks.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Celery background workers. These offload the heavy, latency-sensitive work
(CNN tensor processing, document chunking/embedding, outbound webhook
delivery) off the request/response cycle. Each task updates the owning
InferenceJob row so the frontend can poll for status.

Tasks use a synchronous SQLAlchemy engine (psycopg2) rather than the async
engine used by FastAPI, since Celery workers are synchronous processes.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.celery_app import celery_app
from backend.config import get_settings
from backend.models import InferenceJob, JobStatus

logger = logging.getLogger("omniscale.tasks")
settings = get_settings()

def _derive_sync_url(async_url: str) -> str:
    """Celery workers run outside the asyncio event loop, so they need a
    synchronous driver. Handles both the production Postgres URL and the
    SQLite URL used by the test suite — without this, engine creation
    fails at import time under SQLite (aiosqlite has no sync mode)."""
    if async_url.startswith("postgresql+asyncpg"):
        return async_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    if async_url.startswith("sqlite+aiosqlite"):
        return async_url.replace("sqlite+aiosqlite", "sqlite")
    return async_url


_sync_url = _derive_sync_url(settings.DATABASE_URL)
_sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_sync_engine)


def _mark_job(session: Session, job_id: str, status: JobStatus, result: dict | None = None, error: str | None = None) -> None:
    job = session.get(InferenceJob, job_id)
    if not job:
        logger.warning("Job %s not found when updating status", job_id)
        return
    job.status = status
    if result is not None:
        job.result_json = json.dumps(result)
    if error is not None:
        job.error_message = error
    if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        job.finished_at = datetime.now(timezone.utc)
    session.commit()


@celery_app.task(bind=True, max_retries=3, name="backend.tasks.run_cnn_inference")
def run_cnn_inference(self, job_id: str, image_bytes_b64: str) -> dict:
    """Decode base64 image, run the PyTorch CNN pipeline, persist the result."""
    import base64

    from backend.cnn_module import run_inference

    session = SyncSession()
    try:
        _mark_job(session, job_id, JobStatus.RUNNING)
        image_bytes = base64.b64decode(image_bytes_b64)
        result = run_inference(image_bytes)
        payload = {
            "predictions": [dataclasses.asdict(p) for p in result.predictions],
            "feature_vector_dim": result.feature_vector_dim,
            "device": result.device,
        }
        _mark_job(session, job_id, JobStatus.SUCCEEDED, result=payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.exception("CNN inference failed for job %s", job_id)
        _mark_job(session, job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, countdown=15) from exc
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=3, name="backend.tasks.run_rag_ingest")
def run_rag_ingest(self, job_id: str, namespace: str, filename: str, text: str, document_id: str) -> dict:
    """Chunk + embed a document and add it to the user's vector namespace."""
    from backend.database_sync import update_document_chunk_count
    from backend.rag_engine import ingest_document

    session = SyncSession()
    try:
        _mark_job(session, job_id, JobStatus.RUNNING)
        chunk_count = ingest_document(namespace, filename, text)
        update_document_chunk_count(session, document_id, chunk_count)
        payload = {"chunk_count": chunk_count, "namespace": namespace}
        _mark_job(session, job_id, JobStatus.SUCCEEDED, result=payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.exception("RAG ingest failed for job %s", job_id)
        _mark_job(session, job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, countdown=15) from exc
    finally:
        session.close()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
def _post_webhook(url: str, payload: dict) -> None:
    resp = httpx.post(url, json=payload, timeout=10.0)
    resp.raise_for_status()


@celery_app.task(bind=True, max_retries=5, name="backend.tasks.send_webhook_notification")
def send_webhook_notification(self, url: str, payload: dict) -> bool:
    """Deliver an outbound notification (e.g. billing event) with retries."""
    try:
        _post_webhook(url, payload)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook delivery to %s failed: %s", url, exc)
        raise self.retry(exc=exc, countdown=20) from exc


# ---------------------------------------------------------------------------
# Scheduled (Celery Beat) maintenance tasks — see celery_app.py beat_schedule
# ---------------------------------------------------------------------------
@celery_app.task(name="backend.tasks.cleanup_stale_jobs")
def cleanup_stale_jobs(timeout_minutes: int = 30) -> dict:
    """
    Any InferenceJob left in PENDING/RUNNING past `timeout_minutes` almost
    certainly belongs to a worker that crashed or was killed mid-task —
    without this, such jobs would spin forever in the dashboard. Runs every
    10 minutes via Celery Beat.
    """
    from backend.models import InferenceJob, JobStatus

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    session = SyncSession()
    try:
        stale = (
            session.query(InferenceJob)
            .filter(
                InferenceJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                InferenceJob.created_at < cutoff,
            )
            .all()
        )
        for job in stale:
            job.status = JobStatus.FAILED
            job.error_message = f"Timed out after {timeout_minutes} minutes with no worker response."
            job.finished_at = datetime.now(timezone.utc)
        session.commit()
        if stale:
            logger.info("cleanup_stale_jobs: marked %d job(s) as failed (timeout)", len(stale))
        return {"cleaned_up": len(stale)}
    finally:
        session.close()


@celery_app.task(name="backend.tasks.downgrade_expired_subscriptions")
def downgrade_expired_subscriptions(grace_period_days: int = 3) -> dict:
    """
    A subscription stuck in PAST_DUE for longer than the grace period (card
    failed and was never fixed, a webhook was missed, etc.) is dropped back
    to the FREE tier automatically — paid access should never silently
    persist forever on a failed payment. Runs hourly via Celery Beat.
    """
    from backend.models import Subscription, SubscriptionStatus, SubscriptionTier

    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_period_days)
    session = SyncSession()
    try:
        overdue = (
            session.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.PAST_DUE,
                Subscription.updated_at < cutoff,
            )
            .all()
        )
        for sub in overdue:
            sub.tier = SubscriptionTier.FREE
            sub.status = SubscriptionStatus.CANCELED
        session.commit()
        if overdue:
            logger.info("downgrade_expired_subscriptions: downgraded %d subscription(s)", len(overdue))
        return {"downgraded": len(overdue)}
    finally:
        session.close()
