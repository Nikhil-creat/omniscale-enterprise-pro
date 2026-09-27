"""
backend/routers/agent_router.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent import run_agent
from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.rate_limit import enforce_rate_limit
from backend.schemas import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/invoke", response_model=AgentResponse)
async def invoke_agent(
    payload: AgentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    await enforce_rate_limit(request, user)
    namespace = payload.document_namespace or f"user-{user.id}"
    result = run_agent(payload.prompt, namespace, payload.force_route)
    return AgentResponse(**result)
