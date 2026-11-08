#!/bin/sh
# Старт контейнера: миграции, витрина при первом запуске, затем uvicorn.
set -eu

python -m scripts.migrate
python -m scripts.build_dataset --if-empty

exec uvicorn app:app \
    --host "${LADA_HOST:-0.0.0.0}" \
    --port "${LADA_PORT:-8000}" \
    --workers "${LADA_WORKERS:-2}"
