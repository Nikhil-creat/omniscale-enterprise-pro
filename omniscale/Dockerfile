# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
# Multi-stage build: slim final image, no build toolchain left behind.

FROM python:3.11-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim AS runtime
LABEL maintainer="NIKHIL CHARY SRIRAMOJU" \
      org.opencontainers.image.title="OmniScale Enterprise Pro" \
      org.opencontainers.image.description="Designed and Developed by NIKHIL CHARY SRIRAMOJU"

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY backend ./backend
COPY alembic.ini .

RUN useradd --create-home --uid 1000 omniscale && \
    mkdir -p /app/data/vector_index /app/data/cnn_weights && \
    chown -R omniscale:omniscale /app
USER omniscale

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
