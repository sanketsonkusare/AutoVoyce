# ============================================================
# AutoVoyce Backend — Production Dockerfile
# ============================================================
# Uses Pinecone integrated inference (no local PyTorch needed).
# Runs as non-root user with health check and multi-worker uvicorn.
# ============================================================

FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy dependency file first (cache layer)
COPY requirements.txt .

# Install Python dependencies (no PyTorch needed — Pinecone handles embeddings)
RUN uv pip install --system --no-cache -r requirements.txt


# --- Runtime ---
FROM python:3.12-slim

# Install system dependencies
#   - curl: for Docker health check
#   - ca-certificates: for HTTPS proxy connections (Webshare)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r autovoyce && useradd -r -g autovoyce -d /app -s /sbin/nologin autovoyce

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Own app directory to non-root user
RUN chown -R autovoyce:autovoyce /app

# Switch to non-root user
USER autovoyce

# Expose port
EXPOSE 8000

# Environment defaults (override via docker run -e or .env file)
ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check — hits the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with 4 workers for production concurrency
CMD uvicorn src.main.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 4 \
    --timeout-keep-alive 65 \
    --access-log
