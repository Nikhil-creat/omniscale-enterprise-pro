"""
backend/routers/rag_router.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Document, InferenceJob, JobStatus, User
from backend.rag_engine import retrieve
from backend.rate_limit import enforce_rate_limit
from backend.schemas import DocumentOut, JobOut, RAGQueryRequest, RAGQueryResult
from backend.tasks import run_rag_ingest

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/documents", response_model=JobOut, status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InferenceJob:
    await enforce_rate_limit(request, user)
    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8", errors="ignore")
    namespace = f"user-{user.id}"

    document = Document(user_id=user.id, filename=file.filename or "untitled", vector_namespace=namespace)
    db.add(document)
    await db.flush()

    job = InferenceJob(user_id=user.id, job_type="rag_ingest", status=JobStatus.PENDING)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    async_result = run_rag_ingest.delay(job.id, namespace, document.filename, text, document.id)
    job.celery_task_id = async_result.id
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Document]:
    result = await db.execute(select(Document).where(Document.user_id == user.id))
    return list(result.scalars().all())


@router.post("/query", response_model=list[RAGQueryResult])
async def query_documents(
    payload: RAGQueryRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> list[RAGQueryResult]:
    await enforce_rate_limit(request, user)
    namespace = payload.namespace or f"user-{user.id}"
    chunks = retrieve(namespace, payload.query, top_k=payload.top_k)
    return [
        RAGQueryResult(chunk_text=c.chunk_text, score=c.score, source_document=c.source_document)
        for c in chunks
    ]
