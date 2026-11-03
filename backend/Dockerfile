FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependencies first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code.
COPY app ./app
COPY ingestion ./ingestion
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x docker-entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz').status==200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
