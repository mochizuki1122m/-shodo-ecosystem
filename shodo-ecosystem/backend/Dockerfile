# Multi-stage optimized FastAPI Backend
FROM python:3.11-slim-bullseye AS builder

# Build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-deps -r requirements.txt

# Production runtime
FROM python:3.11-slim-bullseye AS production

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Security: Non-root user
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser

# Python optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY --chown=appuser:appuser ./src /app/src
COPY --chown=appuser:appuser ./alembic.ini /app/
COPY --chown=appuser:appuser ./migrations /app/migrations
COPY --chown=appuser:appuser ./scripts /app/scripts

# Create required directories
RUN mkdir -p /app/logs /app/uploads && \
    chown -R appuser:appuser /app

# Security: Switch to non-root user
USER appuser

# Health check with proper timeout (use lightweight simple endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/simple || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Development target
FROM production AS development
USER root
RUN pip install --no-cache-dir debugpy pytest-xdist
USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production server with optimized settings
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--loop", "uvloop", "--access-log", "--log-level", "info", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "100"]