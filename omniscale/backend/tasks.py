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
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.celery_app import celery_app
from backend.config import get_settings
from backend.models import InferenceJob, JobStatus

logger = logging.getLogger("omniscale.tasks")
settings = get_settings()

_sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
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
