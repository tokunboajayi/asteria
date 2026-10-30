# Asteria engine API: serves prebuilt, hash-verified artifacts (read-only).
# Build from the repository root:  docker build -f engine/Dockerfile -t asteria-api .
# Artifacts are built offline (asteria build / build-orbits) and mounted at /data.
FROM python:3.12-slim AS app

RUN pip install --no-cache-dir "uv==0.11.32"
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/engine
# Dependencies first (cached layer); the optional NRLMSIS "model" extra is NOT installed:
# its MSIS2 code is licensed for academic, non-commercial use only.
COPY engine/pyproject.toml engine/uv.lock engine/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY engine/src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --home-dir /data asteria \
    && mkdir -p /data && chown asteria /data
ENV ASTERIA_HOME=/data \
    PATH=/app/.venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib
USER asteria
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["asteria", "serve", "--host", "0.0.0.0", "--port", "8000"]
