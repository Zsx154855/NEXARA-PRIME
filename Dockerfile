# NEXARA PRIME — external-product deployment image
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXARA_API_HOST=0.0.0.0 \
    NEXARA_MULTI_TENANT=1 \
    NEXARA_DB_PATH=/data/nexara.db \
    NEXARA_WORKSPACE_ROOT=/data/workspace \
    NEXARA_REPORT_ROOT=/data/reports

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY platform/sdk/python ./platform/sdk/python
RUN pip install --no-cache-dir -e ".[test]" \
 && pip install --no-cache-dir -e platform/sdk/python

# Non-root, and the data dir is the only writable location.
RUN useradd --create-home --uid 10001 nexara \
 && mkdir -p /data && chown -R nexara:nexara /data /app
USER nexara
VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "nexara_prime.api:app", "--host", "0.0.0.0", "--port", "8765"]
