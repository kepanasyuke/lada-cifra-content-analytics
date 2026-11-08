"""HTTP-слой проекта «Каталог»."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from projects.catalog_api import service
from projects.catalog_api.sources import (
    CatalogUnavailableError,
    HttpCatalogSource,
    LocalCatalogSource,
)
from shared.db import DictConnection, get_conn
from shared.theme import page

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_class=HTMLResponse)
def catalog_page(request: Request) -> HTMLResponse:
    """Страница проекта «Каталог»."""
    return page(request, "projects/catalog_api/templates/index.html", "catalog")


@router.get("/api/catalog/summary")
def catalog_summary(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Сводка по каталогу."""
    return service.summary(conn)


@router.get("/api/catalog/models")
def catalog_models(
    brand: str = "",
    q: str = "",
    limit: int = Query(50, ge=1, le=500),
    conn: DictConnection = Depends(get_conn),
) -> list[dict[str, Any]]:
    """Поиск по позициям каталога."""
    return service.search_models(conn, brand, q, limit)


@router.get("/api/catalog/brands")
def catalog_brands(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Бренды каталога."""
    return service.brands(conn)


@router.get("/api/catalog/coverage")
def catalog_coverage(
    limit: int = Query(15, ge=1, le=100),
    conn: DictConnection = Depends(get_conn),
) -> list[dict[str, Any]]:
    """Покрытие каталога объявлениями."""
    return service.coverage(conn, limit)


@router.get("/api/catalog/runs")
def catalog_runs(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Журнал запусков ингеста."""
    return service.runs(conn)


@router.post("/api/catalog/ingest")
def catalog_ingest(
    mode: str = Query("local"),
    conn: DictConnection = Depends(get_conn),
) -> dict[str, Any]:
    """Запускает загрузку каталога: local (витрина) или live (HTTP-API)."""
    return ingest_with(conn, mode)


def ingest_with(conn: sqlite3.Connection, mode: str) -> dict[str, Any]:
    """Выбирает источник и запускает ингест."""
    return service.ingest(conn, source_for(conn, mode))


def source_for(conn: sqlite3.Connection, mode: str) -> Any:
    """Источник каталога по режиму запуска."""
    return HttpCatalogSource() if mode == "live" else LocalCatalogSource(conn)


@router.get("/api/catalog/errors")
def catalog_errors() -> dict[str, str]:
    """Подсказка по коду ошибки источника."""
    return {
        "code": CatalogUnavailableError.__name__,
        "hint": "проверьте доступность внешнего API",
    }
