"""
backend/main.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

FastAPI application entrypoint. Wires up CORS, Sentry error tracking,
Prometheus metrics, global exception handling, and every API router.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration

from backend.config import get_settings
from backend.database import init_models
from backend.routers import agent_router, auth_router, billing_router, cnn_router, rag_router

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("omniscale.main")

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.2,
        integrations=[FastApiIntegration()],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s [%s]", settings.APP_NAME, settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "development":
        await init_models()
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Elite, fully automated, multi-tenant AI SaaS platform.",
    version="1.0.0",
    contact={"name": settings.APP_AUTHOR},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_branding(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    response.headers["X-Powered-By"] = f"OmniScale Enterprise Pro — Designed and Developed by {settings.APP_AUTHOR}"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "designed_by": settings.APP_AUTHOR},
    )


if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")


app.include_router(auth_router.router)
app.include_router(agent_router.router)
app.include_router(rag_router.router)
app.include_router(cnn_router.router)
app.include_router(billing_router.router)


@app.get("/")
async def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "designed_and_developed_by": settings.APP_AUTHOR,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.active_llm_provider.value,
        "docs": "/docs",
    }


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
