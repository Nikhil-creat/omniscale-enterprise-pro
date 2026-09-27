"""
backend/schemas.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Pydantic v2 request/response contracts for every API surface.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


# ---------- API keys ----------
class APIKeyCreate(BaseModel):
    name: str = Field(default="default", max_length=120)


class APIKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime


class APIKeyCreated(APIKeyOut):
    plaintext_key: str  # returned exactly once


# ---------- Agent ----------
class AgentRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    document_namespace: Optional[str] = None
    force_route: Optional[Literal["rag", "cnn", "chat"]] = None


class AgentResponse(BaseModel):
    route_taken: Literal["rag", "cnn", "chat"]
    answer: str
    provider: str
    sources: list[str] = []
    latency_ms: float


# ---------- RAG ----------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    chunk_count: int
    vector_namespace: str
    created_at: datetime


class RAGQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    namespace: str
    top_k: int = Field(default=5, ge=1, le=20)


class RAGQueryResult(BaseModel):
    chunk_text: str
    score: float
    source_document: str


# ---------- CNN / jobs ----------
class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_type: str
    status: str
    celery_task_id: Optional[str] = None
    result_json: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


# ---------- Billing ----------
class CheckoutSessionRequest(BaseModel):
    tier: Literal["pro", "enterprise"]


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tier: str
    status: str
    current_period_end: Optional[datetime] = None


class UsageMetrics(BaseModel):
    tier: str
    requests_this_minute: int
    requests_limit_per_minute: int
    documents_indexed: int
    jobs_last_24h: int


class WebhookAck(BaseModel):
    received: bool = True
    event_type: Optional[str] = None
    detail: Optional[dict[str, Any]] = None
