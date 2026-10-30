#!/bin/sh
# Container entrypoint: optionally seed CORTEX memory, then serve the API.
# Schema is created automatically on app startup (db.init_db); ingestion is
# guarded by --if-empty so restarts don't re-ingest.
set -e

if [ "${INGEST_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] ingesting site=${INGEST_SITE:-hirebuddha} (if empty)…"
  python -m ingestion.ingest --site "${INGEST_SITE:-hirebuddha}" --if-empty \
    || echo "[entrypoint] ingestion skipped/failed — continuing to serve"
fi

echo "[entrypoint] starting uvicorn on :${PORT:-8080}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
