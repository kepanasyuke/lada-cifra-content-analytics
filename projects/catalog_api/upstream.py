"""Эмулятор внешнего каталога: отдаёт JSON-каталог по HTTP, как сторонний сервис.

Каталог собирается из витрины объявлений: уникальные комбинации
бренд + модель + комплектация + топливо + коробка с усреднёнными характеристиками.
Роутер монтируется в приложение по пути /upstream, поэтому ингест в проекте 1
проходит честный сетевой путь: HTTP-запрос, пагинация, ретраи, разбор JSON.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query

from shared.db import DictConnection, get_conn, scalar

router = APIRouter(prefix="/upstream", tags=["upstream"])

CATALOG_SQL = """
SELECT
    brand,
    model,
    trim,
    fuel,
    transmission,
    MIN(year)                       AS year_from,
    MAX(year)                       AS year_to,
    CAST(ROUND(AVG(engine_cc)) AS INTEGER) AS engine_cc,
    ROUND(AVG(power_bhp), 1)        AS power_bhp,
    CAST(ROUND(AVG(seats)) AS INTEGER)    AS seats,
    COUNT(*)                        AS offers
FROM offers
GROUP BY brand, model, trim, fuel, transmission
ORDER BY brand, model, trim, fuel, transmission
"""


def catalog_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Полный каталог из витрины."""
    return [dict(row) for row in conn.execute(CATALOG_SQL).fetchall()]


def external_id(item: dict[str, Any]) -> str:
    """Стабильный идентификатор позиции каталога."""
    parts = (item["brand"], item["model"], item["trim"], item["fuel"], item["transmission"])
    return "-".join(str(part).strip().lower().replace(" ", "_") for part in parts)


def enrich(item: dict[str, Any]) -> dict[str, Any]:
    """Добавляет идентификатор к позиции каталога."""
    return {**item, "id": external_id(item)}


def page_count(page_size: int, total: int) -> int:
    """Сколько страниц нужно на весь каталог."""
    return max(1, -(-total // page_size))


def page_bounds(page: int, page_size: int, total: int) -> tuple[int, int, int]:
    """Границы среза и общее число страниц."""
    start = (page - 1) * page_size
    return start, start + page_size, page_count(page_size, total)


def payload_of(rows: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    """Собирает страницу каталога из полного списка."""
    start, stop, pages = page_bounds(page, page_size, len(rows))
    return {
        "page": page,
        "pages": pages,
        "total": len(rows),
        "page_size": page_size,
        "items": [enrich(item) for item in rows[start:stop]],
    }


def catalog_payload(
    conn: sqlite3.Connection,
    page: int = 1,
    page_size: int = 500,
) -> dict[str, Any]:
    """Собирает ответ API каталога: items + метаданные пагинации."""
    return payload_of(catalog_rows(conn), page, page_size)


@router.get("/v1/catalog")
def catalog_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=2000),
    conn: DictConnection = Depends(get_conn),
) -> dict[str, Any]:
    """Выдача каталога с пагинацией."""
    return catalog_payload(conn, page, page_size)


TOTAL_SQL = (
    "SELECT COUNT(*) FROM "
    "(SELECT 1 FROM offers GROUP BY brand, model, trim, fuel, transmission)"
)


@router.get("/v1/catalog/total")
def catalog_total(conn: DictConnection = Depends(get_conn)) -> dict[str, int]:
    """Общее число позиций каталога."""
    return {"total": int(scalar(conn, TOTAL_SQL) or 0)}
