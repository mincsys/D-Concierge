# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS frontend-builder

WORKDIR /app/src/frontend

RUN npm install -g @openai/codex@0.128.0

COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci

COPY src/frontend/ ./
RUN npm run build

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /usr/local/bin/uv
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-builder /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -sf /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex

COPY pyproject.toml uv.lock alembic.ini ./
RUN uv sync --frozen --no-dev

COPY src/backend/ ./src/backend/
COPY codex/output_json_schema/ ./codex/output_json_schema/
COPY --from=frontend-builder /app/src/frontend/dist/ ./src/backend/app/static/dist/

EXPOSE 8000

CMD [".venv/bin/uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
