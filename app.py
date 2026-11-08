"""Единое приложение контент-аналитики: пять сервисов в одном процессе.

Запуск: uvicorn app:app --reload  →  http://127.0.0.1:8000/catalog
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from projects.catalog_api.api import router as catalog_router
from projects.catalog_api.upstream import router as upstream_router
from projects.content_qa.api import router as qa_router
from projects.demand_forecast.api import router as forecast_router
from projects.matrix_optimizer.api import router as matrix_router
from projects.trend_radar.api import router as trends_router
from shared.config import APP_TITLE, STATIC_DIR
from shared.db import connect, scalar

ROUTERS = (
    catalog_router,
    upstream_router,
    qa_router,
    trends_router,
    matrix_router,
    forecast_router,
)

app = FastAPI(
    title=APP_TITLE, version="1.0.0", description="Пять сервисов контент-аналитики автобизнеса"
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

for router in ROUTERS:
    app.include_router(router)


@app.get("/")
def index() -> RedirectResponse:
    """Корень приложения ведёт на первый проект."""
    return RedirectResponse("/catalog")


@app.get("/health")
def health() -> dict[str, object]:
    """Проверка живости и наличия витрины."""
    return with_connection(counts)


def with_connection(action: Callable[[Any], dict[str, object]]) -> dict[str, object]:
    """Выполняет действие в коротком соединении с витриной."""
    conn = connect()
    try:
        return action(conn)
    finally:
        conn.close()


def report_of(offers: object, catalog: object) -> dict[str, object]:
    """Тело ответа health-проверки."""
    return {"status": "ok", "offers": offers, "catalog": catalog, "projects": len(ROUTERS) - 1}


def counts(conn: Any) -> dict[str, object]:
    """Счётчики витрины для health-проверки."""
    offers = scalar(conn, "SELECT COUNT(*) FROM offers")
    return report_of(offers, scalar(conn, "SELECT COUNT(*) FROM catalog_models"))
