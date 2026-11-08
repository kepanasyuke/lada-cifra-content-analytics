FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LADA_ENV=prod \
    LADA_DATA_DIR=/data \
    LADA_CSV=/app/data/raw/car_details_v3.csv \
    LADA_WAREHOUSE=/data/warehouse.sqlite \
    LADA_HOST=0.0.0.0 \
    LADA_PORT=8000 \
    LADA_WORKERS=2

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py pyproject.toml ./
COPY shared ./shared
COPY projects ./projects
COPY scripts ./scripts
COPY sql ./sql
COPY data/raw ./data/raw
COPY docker ./docker

RUN chmod +x /app/docker/entrypoint.sh && mkdir -p /data && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["/app/docker/entrypoint.sh"]
