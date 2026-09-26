"""
backend/celery_app.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Celery application instance. Workers are launched with:
    celery -A backend.celery_app worker --loglevel=info -Q default,cnn,rag
"""
from __future__ import annotations

from celery import Celery

from backend.config import get_settings

settings = get_settings()

celery_app = Celery(
    "omniscale",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.tasks.run_cnn_inference": {"queue": "cnn"},
        "backend.tasks.run_rag_ingest": {"queue": "rag"},
        "backend.tasks.send_webhook_notification": {"queue": "default"},
    },
    task_default_retry_delay=10,
)
