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
        "backend.tasks.cleanup_stale_jobs": {"queue": "default"},
        "backend.tasks.downgrade_expired_subscriptions": {"queue": "default"},
        "backend.tasks.sync_subscription_periods": {"queue": "default"},
    },
    task_default_retry_delay=10,
    beat_schedule={
        # Marks jobs stuck in pending/running past a timeout as failed, so
        # the dashboard never shows a job spinning forever because a worker
        # crashed mid-task.
        "cleanup-stale-jobs-every-10-min": {
            "task": "backend.tasks.cleanup_stale_jobs",
            "schedule": 600.0,
        },
        # Grace-period downgrade: a subscription left in `past_due` for too
        # long (card failed, webhook missed, etc.) is automatically dropped
        # back to the free tier rather than silently granting paid access
        # forever.
        "downgrade-expired-subscriptions-hourly": {
            "task": "backend.tasks.downgrade_expired_subscriptions",
            "schedule": 3600.0,
        },
    },
)
