"""Проверки качества контента: полнота карточек, дубли, выбросы, связь с каталогом."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from projects.content_qa.rules import FIELD_RULES, FieldRule
from shared.db import Row, fetch_all, fetch_one, scalar

IQR_FACTOR = 1.5
PRICE_FLOOR = 10000
MIN_YEAR = 1990
MAX_KM = 700000
BASE_COLUMNS = "offer_id, brand, model, name"
PRICE_SQL = f"SELECT {BASE_COLUMNS}, price FROM offers WHERE price < ? OR price > ?"  # noqa: S608
RANGE_SQL = (
    f"SELECT {BASE_COLUMNS}, year, km_driven FROM offers "  # noqa: S608
    "WHERE year < ? OR year > ? OR km_driven > ?"
)

DUPLICATE_SQL = (
    f"SELECT {BASE_COLUMNS}, COUNT(*) AS copies FROM offers "  # noqa: S608
    "GROUP BY name, year, km_driven, price HAVING COUNT(*) > 1"
)

UNMATCHED_SQL = """
SELECT o.offer_id, o.brand, o.model, o.name
FROM offers o
LEFT JOIN catalog_models c ON c.brand = o.brand AND c.model = o.model
WHERE c.catalog_id IS NULL
"""

METRICS_SQL = """
SELECT
    COUNT(*)                                              AS offers,
    ROUND(100.0 * SUM(engine_cc IS NULL) / COUNT(*), 2)    AS missing_engine_pct,
    ROUND(100.0 * SUM(power_bhp IS NULL) / COUNT(*), 2)    AS missing_power_pct,
    ROUND(100.0 * SUM(seats IS NULL) / COUNT(*), 2)        AS missing_seats_pct,
    ROUND(AVG(completeness_pct), 2)                       AS completeness_pct
FROM v_offers
"""


def finding(code: str, severity: str, scope: str, row: Row, message: str) -> dict[str, Any]:
    """Собирает запись о нарушении."""
    return {
        "rule_code": code,
        "severity": severity,
        "scope": scope,
        "offer_id": row.get("offer_id"),
        "brand": row.get("brand") or "",
        "model": row.get("model") or "",
        "message": message,
    }


def describe(rule: FieldRule, row: Row) -> str:
    """Текст нарушения для проверки поля."""
    return f"{rule.message}: {row.get('name', '')}"


def field_findings(conn: Any, rule: FieldRule) -> list[dict[str, Any]]:
    """Нарушения по одному обязательному полю."""
    return [
        finding(rule.code, rule.severity, "field", row, describe(rule, row))
        for row in fetch_all(conn, rule.sql())
    ]


def all_field_findings(conn: Any) -> list[dict[str, Any]]:
    """Нарушения по всем полям."""
    return [item for rule in FIELD_RULES for item in field_findings(conn, rule)]


def quartiles(conn: Any) -> list[float]:
    """Квартили распределения цен."""
    return statistics.quantiles(prices(conn), n=4)


def prices(conn: Any) -> list[int]:
    """Все цены витрины."""
    return [row["price"] for row in fetch_all(conn, "SELECT price FROM offers")]


def spread_of(first: float, third: float) -> float:
    """Полуширина коридора по правилу IQR."""
    return IQR_FACTOR * (third - first)


def price_bounds(conn: Any) -> tuple[float, float]:
    """Границы нормальных цен по правилу 1.5·IQR."""
    first, _, third = quartiles(conn)
    return first - spread_of(first, third), third + spread_of(first, third)


def outlier_finding(row: Row) -> dict[str, Any]:
    """Нарушение по одной аномальной цене."""
    note = f"цена вне коридора: {row['price']}"
    return finding("QA-PRICE-OUTLIER", "bad", "price", row, note)


def outlier_findings(rows: list[Row]) -> list[dict[str, Any]]:
    """Нарушения по строкам с аномальной ценой."""
    return [outlier_finding(row) for row in rows]


def price_findings(conn: Any) -> list[dict[str, Any]]:
    """Цены вне статистического коридора."""
    low, high = price_bounds(conn)
    return outlier_findings(fetch_all(conn, PRICE_SQL, (max(low, PRICE_FLOOR), high)))


def duplicate_findings(conn: Any) -> list[dict[str, Any]]:
    """Дубли карточек по названию, году, пробегу и цене."""
    rows = fetch_all(conn, DUPLICATE_SQL)
    return [
        finding("QA-DUPLICATE", "warn", "duplicate", row, f"копий карточки: {row['copies']}")
        for row in rows
    ]


def range_findings(conn: Any) -> list[dict[str, Any]]:
    """Невозможные значения года выпуска и пробега."""
    rows = fetch_all(conn, RANGE_SQL, (MIN_YEAR, current_year(), MAX_KM))
    return [
        finding("QA-RANGE", "bad", "range", row, f"год {row['year']}, пробег {row['km_driven']}")
        for row in rows
    ]


def current_year() -> int:
    """Текущий год для проверки свежести."""
    return datetime.now(UTC).year


def catalog_findings(conn: Any) -> list[dict[str, Any]]:
    """Объявления без позиции во внешнем каталоге."""
    return [
        finding("QA-CATALOG-MISS", "warn", "catalog", row, "модели нет в каталоге")
        for row in fetch_all(conn, UNMATCHED_SQL)
    ]


def collect(conn: Any) -> list[dict[str, Any]]:
    """Полный прогон всех правил."""
    return [
        *all_field_findings(conn),
        *price_findings(conn),
        *duplicate_findings(conn),
        *range_findings(conn),
        *catalog_findings(conn),
    ]


def duplicates_pct(conn: Any) -> float:
    """Доля дублирующихся карточек."""
    total = scalar(conn, "SELECT COUNT(*) FROM offers") or 1
    return round(100.0 * len(duplicate_findings(conn)) / total, 2)


def price_outliers_pct(conn: Any) -> float:
    """Доля ценовых выбросов."""
    total = scalar(conn, "SELECT COUNT(*) FROM offers") or 1
    return round(100.0 * len(price_findings(conn)) / total, 2)


def catalog_unmatched_pct(conn: Any) -> float:
    """Доля объявлений без связи с каталогом."""
    total = scalar(conn, "SELECT COUNT(*) FROM offers") or 1
    return round(100.0 * len(catalog_findings(conn)) / total, 2)


def metrics(conn: Any) -> dict[str, float]:
    """Метрики качества контента для дашборда и алертов."""
    base = fetch_one(conn, METRICS_SQL) or {}
    return {
        **{key: float(value or 0) for key, value in base.items()},
        "duplicates_pct": duplicates_pct(conn),
        "price_outliers_pct": price_outliers_pct(conn),
        "catalog_unmatched_pct": catalog_unmatched_pct(conn),
    }
