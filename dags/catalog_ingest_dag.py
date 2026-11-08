"""DAG 1: сбор внешнего каталога автомобилей.

Расписание: ежедневно в 05:30. Задача идемпотентна: повторный запуск обновляет
позиции каталога по ключу (бренд, модель, комплектация, топливо, КПП).
"""

from __future__ import annotations

from airflow.decorators import dag, task
from pendulum import datetime

from projects.catalog_api.service import ingest, summary
from projects.catalog_api.sources import LocalCatalogSource
from shared.db import connect


@dag(
    dag_id="catalog_ingest",
    schedule="30 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["catalog", "content"],
    doc_md="Сбор внешнего каталога и запись в витрину контент-аналитики.",
)
def catalog_ingest_pipeline():
    """Пайплайн загрузки каталога."""

    @task(retries=3, retry_delay=60)
    def load_catalog() -> dict:
        """Загружает каталог и возвращает отчёт."""
        conn = connect()
        try:
            return ingest(conn, LocalCatalogSource(conn))
        finally:
            conn.close()

    @task
    def assert_volume(report: dict) -> dict:
        """Проверяет, что загрузка не выродилась в пустой каталог."""
        conn = connect()
        try:
            totals = summary(conn)
        finally:
            conn.close()
        if int(totals.get("trims") or 0) == 0:
            raise ValueError("каталог пуст после загрузки")
        return {**report, "trims": totals.get("trims")}

    assert_volume(load_catalog())


catalog_ingest_pipeline()
