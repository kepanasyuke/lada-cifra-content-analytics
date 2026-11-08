"""DAG 2: контроль качества контента и алерты.

Расписание: каждое утро в 06:15 после загрузки каталога. Прогон проверок
пишет нарушения и алерты в витрину; при наличии критичных алертов задача
падает, чтобы сработал стандартный механизм уведомлений Airflow.
"""

from __future__ import annotations

from airflow.decorators import dag, task
from pendulum import datetime

from projects.content_qa.service import alerts_of, run_qa
from shared.db import connect


@dag(
    dag_id="content_quality",
    schedule="15 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["content", "qa", "alerts"],
    doc_md="Проверки полноты и качества контента, пороговые алерты.",
)
def content_quality_pipeline():
    """Пайплайн проверок качества."""

    @task(retries=2, retry_delay=120)
    def run_checks() -> dict:
        """Прогоняет все правила качества."""
        conn = connect()
        try:
            return run_qa(conn)
        finally:
            conn.close()

    @task
    def escalate(report: dict) -> dict:
        """Поднимает ошибку, если есть критичные алерты."""
        conn = connect()
        try:
            critical = [item for item in alerts_of(conn) if item["level"] == "bad"]
        finally:
            conn.close()
        if critical:
            raise ValueError(f"критичных алертов: {len(critical)}")
        return report

    escalate(run_checks())


content_quality_pipeline()
