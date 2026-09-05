# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the Next.js static export
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

# Copy dependency manifests first so this layer caches independently of source changes.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# uv installs itself into /usr/local/bin via the official static binary image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV FINALLY_DB_PATH=/app/db/finally.db \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# Dependency manifests first for layer caching. pyproject.toml declares
# readme = "README.md", so it must be present before `uv sync` resolves the project.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# Now bring in the application source and finish installing the project itself.
COPY backend/ ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Static frontend export served by FastAPI.
COPY --from=frontend-build /app/frontend/out ./static

# Runtime data directory: SQLite file lives here, volume-mounted in production.
RUN mkdir -p /app/db

# Run as a non-root user; make sure it owns the db directory and the venv it needs to write
# bytecode caches into.
RUN groupadd --system finally && useradd --system --gid finally --home /app finally \
    && chown -R finally:finally /app
USER finally

EXPOSE 8000

# Respect $PORT if set (defaults to 8000) for both the healthcheck and the server itself.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health', timeout=3).status == 200 else 1)"

# `exec` replaces the shell with uvicorn itself (PID 1), so `docker stop`'s SIGTERM reaches
# it directly instead of being absorbed by an un-exec'd shell/wrapper process. Calling
# `uvicorn` straight off PATH (the venv is already synced into the image) avoids adding
# `uv run` as another such layer. --timeout-graceful-shutdown keeps `docker stop` prompt
# even with a live SSE client connected: uvicorn otherwise waits indefinitely for that
# connection to close, burning the full stop grace period and getting SIGKILLed before its
# lifespan shutdown can run.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 5"]
