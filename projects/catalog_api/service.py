"""Сервис проекта «Каталог»: ингест внешнего каталога и выборки для интерфейса."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from projects.catalog_api.sources import CatalogPage, CatalogSource, fetch_catalog, source_name
from shared.db import Row, execute, executemany, fetch_all, fetch_one, scalar

UPSERT_SQL = """
INSERT INTO catalog_models
    (brand, model, trim, year_from, year_to, fuel, transmission,
     engine_cc, power_bhp, seats, external_id, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (brand, model, trim, fuel, transmission) DO UPDATE SET
    year_from  = excluded.year_from,
    year_to    = excluded.year_to,
    engine_cc  = excluded.engine_cc,
    power_bhp = excluded.power_bhp,
    seats      = excluded.seats,
    external_id = excluded.external_id,
    updated_at = excluded.updated_at
"""

MODEL_COLUMNS = (
    "brand",
    "model",
    "trim",
    "year_from",
    "year_to",
    "fuel",
    "transmission",
    "engine_cc",
    "power_bhp",
    "seats",
    "external_id",
    "updated_at",
)

MODELS_SQL = (
    "SELECT * FROM catalog_models WHERE "
    "{where} ORDER BY brand, model, trim LIMIT ?"
)

BRANDS_SQL = (
    "SELECT brand, COUNT(*) AS trims, COUNT(DISTINCT model) AS models "
    "FROM catalog_models GROUP BY brand ORDER BY trims DESC"
)


def now() -> str:
    """Текущий момент в ISO-формате."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def start_run(conn: sqlite3.Connection, source: str) -> int:
    """Регистрирует запуск ингеста."""
    execute(conn, "INSERT INTO ingest_runs (started_at, source) VALUES (?, ?)", (now(), source))
    return int(scalar(conn, "SELECT last_insert_rowid()") or 0)


def spec_values(item: dict[str, Any]) -> tuple[Any, ...]:
    """Технические поля позиции каталога."""
    return (
        item.get("year_from"),
        item.get("year_to"),
        str(item.get("fuel") or ""),
        str(item.get("transmission") or ""),
        item.get("engine_cc"),
        item.get("power_bhp"),
        item.get("seats"),
    )


def model_row(item: dict[str, Any]) -> tuple[Any, ...]:
    """Строка для UPSERT из позиции каталога."""
    head = (str(item.get("brand") or ""), str(item.get("model") or ""), str(item.get("trim") or ""))
    return (*head, *spec_values(item), str(item.get("id") or ""), now())


def save_models(conn: sqlite3.Connection, items: list[dict[str, Any]]) -> int:
    """Сохраняет позиции каталога, обновляя дубли."""
    return executemany(conn, UPSERT_SQL, [model_row(item) for item in items])


def finish_run(conn: sqlite3.Connection, run_id: int, pages: list[CatalogPage]) -> dict[str, Any]:
    """Закрывает журнал запуска и возвращает отчёт."""
    written = save_models(conn, [item for page in pages for item in page.items])
    return close_run(conn, run_id, pages, written)


def close_run(
    conn: sqlite3.Connection, run_id: int, pages: list[CatalogPage], written: int
) -> dict[str, Any]:
    """Фиксирует итог запуска в журнале."""
    execute(
        conn,
        "UPDATE ingest_runs SET finished_at=?, pages=?, records=?, status='ok' WHERE run_id=?",
        (now(), len(pages), written, run_id),
    )
    return {"run_id": run_id, "pages": len(pages), "records": written}


def ingest(conn: sqlite3.Connection, source: CatalogSource) -> dict[str, Any]:
    """Полный цикл загрузки внешнего каталога."""
    run_id = start_run(conn, source_name(source))
    return finish_run(conn, run_id, fetch_catalog(source))


SUMMARY_SQL = (
    "SELECT COUNT(*) AS trims, COUNT(DISTINCT brand) AS brands, "
    "COUNT(DISTINCT model) AS models FROM catalog_models"
)


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Сводка по загруженному каталогу."""
    return {**(fetch_one(conn, SUMMARY_SQL) or {}), "last_run": last_run(conn)}


def last_run(conn: sqlite3.Connection) -> Row:
    """Последний запуск ингеста."""
    return fetch_one(conn, "SELECT * FROM ingest_runs ORDER BY run_id DESC LIMIT 1") or {}


def runs(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    """История запусков ингеста."""
    return fetch_all(conn, "SELECT * FROM ingest_runs ORDER BY run_id DESC LIMIT ?", (limit,))


def brand_condition(brand: str) -> list[tuple[str, list[Any]]]:
    """Условие фильтра по бренду."""
    return [("brand = ?", [brand])] if brand else []


SEARCH_TEXT = "(lower(model) LIKE ? OR lower(trim) LIKE ?)"


def search_condition(query: str) -> list[tuple[str, list[Any]]]:
    """Условие поиска по модели и комплектации."""
    pattern = f"%{query.lower()}%"
    return [(SEARCH_TEXT, [pattern, pattern])] if query else []


def where_text(conditions: list[tuple[str, list[Any]]]) -> str:
    """Текст WHERE из набора условий."""
    return " AND ".join(text for text, _ in conditions) or "1=1"


def where_params(conditions: list[tuple[str, list[Any]]]) -> list[Any]:
    """Параметры условий в порядке подстановки."""
    return [value for _, values in conditions for value in values]


def filter_clause(brand: str, query: str) -> tuple[str, list[Any]]:
    """Собирает WHERE и параметры поиска."""
    conditions = brand_condition(brand) + search_condition(query)
    return where_text(conditions), where_params(conditions)


def models_query(brand: str, query: str, limit: int) -> tuple[str, tuple[Any, ...]]:
    """Собирает SQL поиска по каталогу."""
    where, params = filter_clause(brand, query)
    return MODELS_SQL.format(where=where), (*params, limit)


def search_models(
    conn: sqlite3.Connection,
    brand: str = "",
    query: str = "",
    limit: int = 50,
) -> list[Row]:
    """Поиск позиций каталога."""
    return fetch_all(conn, *models_query(brand, query, limit))


def brands(conn: sqlite3.Connection) -> list[Row]:
    """Бренды с числом позиций каталога."""
    return fetch_all(conn, BRANDS_SQL)


def coverage(conn: sqlite3.Connection, limit: int = 15) -> list[Row]:
    """Покрытие каталога живыми объявлениями: где контент есть, а предложения нет."""
    return fetch_all(
        conn,
        "SELECT * FROM v_catalog_gap ORDER BY offers_per_trim ASC, catalog_trims DESC LIMIT ?",
        (limit,),
    )


def catalog_size(conn: sqlite3.Connection) -> int:
    """Число позиций каталога."""
    return int(scalar(conn, "SELECT COUNT(*) FROM catalog_models") or 0)
