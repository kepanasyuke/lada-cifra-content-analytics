"""Единое приложение контент-аналитики: пять сервисов в одном процессе.

Запуск: uvicorn app:app --reload  →  http://127.0.0.1:8000/catalog
Настройки: LADA_ENV, LADA_LOG_LEVEL, LADA_DATA_DIR, LADA_WAREHOUSE, LADA_PORT.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from projects.catalog_api.api import router as catalog_router
from projects.catalog_api.upstream import router as upstream_router
from projects.content_qa.api import router as qa_router
from projects.demand_forecast.api import router as forecast_router
from projects.matrix_optimizer.api import router as matrix_router
from projects.trend_radar.api import router as trends_router
from shared.config import APP_TITLE, ENVIRONMENT, LOG_LEVEL, STATIC_DIR
from shared.db import connect, scalar
from shared.logs import configure, log_request

LOGGER = configure(LOG_LEVEL)

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


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Логирует каждый запрос с длительностью обработки."""
    return await timed_request(request, call_next)


async def timed_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Запоминает момент начала обработки."""
    started = time.perf_counter()
    return await handled(request, call_next, started)


async def handled(
    request: Request, call_next: Callable[[Request], Awaitable[Response]], started: float
) -> Response:
    """Получает ответ приложения."""
    response = await call_next(request)
    return recorded(request, response, started)


def recorded(request: Request, response: Response, started: float) -> Response:
    """Пишет событие о запросе и отдаёт ответ."""
    log_request(request.method, request.url.path, response.status_code, elapsed(started))
    return response


def elapsed(started: float) -> float:
    """Сколько секунд длилась обработка запроса."""
    return time.perf_counter() - started


@app.get("/")
def index() -> RedirectResponse:
    """Корень приложения ведёт на первый проект."""
    return RedirectResponse("/catalog")


@app.get("/health")
def health() -> dict[str, object]:
    """Проверка живости и наличия витрины."""
    return with_connection(counts)


@app.get("/ready")
def ready() -> Response:
    """Готовность к трафику: миграции и наполнение витрины."""
    report = with_connection(readiness)
    return JSONResponse(report, status_code=ready_code(report))


def ready_code(report: dict[str, object]) -> int:
    """200 для готового приложения, 503 для неготового."""
    return 200 if report["status"] == "ready" else 503


def with_connection(action: Callable[[Any], dict[str, object]]) -> dict[str, object]:
    """Выполняет действие в коротком соединении с витриной."""
    conn = connect()
    try:
        return action(conn)
    finally:
        conn.close()


def safe_scalar(conn: Any, sql: str) -> int | None:
    """Значение запроса или None, если таблицы ещё нет."""
    with contextlib.suppress(sqlite3.Error):
        return int(scalar(conn, sql) or 0)


def counts(conn: Any) -> dict[str, object]:
    """Счётчики витрины для health-проверки."""
    offers = safe_scalar(conn, "SELECT COUNT(*) FROM offers")
    return report_of(offers, safe_scalar(conn, "SELECT COUNT(*) FROM catalog_models"))


def report_of(offers: object, catalog: object) -> dict[str, object]:
    """Тело ответа health-проверки."""
    status = "ok" if offers is not None else "degraded"
    return {
        "status": status,
        "offers": offers,
        "catalog": catalog,
        "environment": ENVIRONMENT,
        "projects": len(ROUTERS) - 1,
    }


MIGRATIONS_SQL = "SELECT COUNT(*) FROM schema_migrations"


def readiness(conn: Any) -> dict[str, object]:
    """Готовность к трафику: применённые миграции и объявления."""
    migrations = safe_scalar(conn, MIGRATIONS_SQL)
    return readiness_report(migrations, safe_scalar(conn, "SELECT COUNT(*) FROM offers"))


def readiness_report(migrations: int | None, offers: int | None) -> dict[str, object]:
    """Тело ответа /ready."""
    return {
        "status": "ready" if migrations and offers else "not-ready",
        "migrations": migrations,
        "offers": offers,
    }
