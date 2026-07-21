#Stage 1: Builder
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

#Stage 2: Runner
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/runtime

COPY --from=builder /root/.local /root/.local
COPY backend/ .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434/api/generate
ENV SENTINEL_DATABASE_PATH=/app/runtime/sentinel_storage.db

VOLUME ["/app/runtime"]

EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
