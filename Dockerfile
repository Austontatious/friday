# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps (keep minimal; add build-essential only if you hit wheels needing compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && python -m pip install -r /app/requirements.txt

# Copy app code
COPY backend/ /app/backend/
COPY core/ /app/core/
COPY sketchmath/ /app/sketchmath/
COPY scripts/ /app/scripts/
COPY start.sh /app/start.sh
COPY pytest.ini /app/pytest.ini
COPY tests/ /app/tests/

# Create non-root user
RUN useradd -m -u 10001 appuser
USER appuser

EXPOSE 9001

# --- Production image ---
FROM base AS prod

# gunicorn for production; bind to 0.0.0.0:9001, respect FRIDAY_API_PORT if set
# backend.main:app must exist; report says it does
CMD ["bash", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${FRIDAY_WEB_CONCURRENCY:-2} -b 0.0.0.0:${FRIDAY_API_PORT:-9001} backend.main:app"]

# --- Dev image ---
FROM base AS dev
USER appuser
CMD ["bash", "-lc", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${FRIDAY_API_PORT:-9001} --reload"]
