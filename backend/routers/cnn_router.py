"""
backend/routers/cnn_router.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import InferenceJob, JobStatus, User
from backend.rate_limit import enforce_rate_limit
from backend.schemas import JobOut
from backend.tasks import run_cnn_inference

router = APIRouter(prefix="/api/v1/cnn", tags=["cnn"])

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze", response_model=JobOut, status_code=202)
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InferenceJob:
    await enforce_rate_limit(request, user)
    raw_bytes = await file.read()
    if len(raw_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10MB limit")

    job = InferenceJob(user_id=user.id, job_type="cnn", status=JobStatus.PENDING)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    encoded = base64.b64encode(raw_bytes).decode("ascii")
    async_result = run_cnn_inference.delay(job.id, encoded)
    job.celery_task_id = async_result.id
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> InferenceJob:
    job = await db.get(InferenceJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
