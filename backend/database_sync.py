"""
backend/database_sync.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Small synchronous DB helpers used exclusively by Celery workers, which run
outside the async event loop that powers the FastAPI app.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import Document


def update_document_chunk_count(session: Session, document_id: str, chunk_count: int) -> None:
    doc = session.get(Document, document_id)
    if doc:
        doc.chunk_count = chunk_count
        session.commit()
