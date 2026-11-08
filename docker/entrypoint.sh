#!/bin/sh
# Старт контейнера: миграции, витрина при первом запуске, затем uvicorn.
set -eu

WAREHOUSE="${LADA_WAREHOUSE:-/data/warehouse.sqlite}"

python -m scripts.migrate

if [ ! -f "$WAREHOUSE" ]; then
    python -m scripts.build_dataset
fi

exec uvicorn app:app \
    --host "${LADA_HOST:-0.0.0.0}" \
    --port "${LADA_PORT:-8000}" \
    --workers "${LADA_WORKERS:-2}"
