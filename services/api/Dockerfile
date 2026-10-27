# API image. Build from services/api:  docker build -t lumiant-api .  (verification status: docs/06-operations/PRODUCTION_READINESS.md)
# /data is the writable, non-root-owned location for generated data and the SQLite app DB (mount a volume there).
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres --extra redis
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY config ./config
RUN uv sync --frozen --no-dev --extra postgres --extra redis

FROM python:3.13-slim
RUN useradd --system --uid 10001 --no-create-home lumiant \
    && mkdir /data && chown lumiant /data
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    LUMIANT_APP_ENV=production \
    LUMIANT_AUTH_MODE=oidc \
    LUMIANT_COOKIE_SECURE=true \
    LUMIANT_DATA_DIR=/data
# Secrets (LUMIANT_APP_DB_URL, warehouse credentials via tenant secret_ref) are injected at run time, never baked in.
USER lumiant
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
# Set FORWARDED_ALLOW_IPS to the proxy's address so client addresses (rate limiting) are read from X-Forwarded-For.
CMD ["uvicorn", "--factory", "lumiant.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
