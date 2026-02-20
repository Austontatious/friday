# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
  && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
 && python -m pip install "git+https://github.com/austontatious/muninn.git"

RUN useradd -m -u 10002 muninn
RUN mkdir -p /data && chown -R muninn:muninn /data
USER muninn

WORKDIR /home/muninn
EXPOSE 8000

CMD ["python", "-m", "muninn.cli", "up", "--host", "0.0.0.0", "--port", "8000", "--db-path", "/data/muninn.db", "--log-level", "info"]
