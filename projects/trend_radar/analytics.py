"""Аналитика трендов: временные ряды, доли, корреляции, индексы цен.

Реализация без pandas и numpy: агрегаты считает SQLite, статистику — stdlib.
Такой расчёт предсказуем по памяти и работает на больших выборках.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from shared.db import Row, fetch_all, fetch_one

SAMPLE_LIMIT = 4000
TOP_BRANDS = 6
MOVERS_WINDOW = 6

TOP_BRANDS_SQL = (
    "SELECT brand, COUNT(*) AS offers FROM v_offers "
    "WHERE period >= ? GROUP BY brand ORDER BY offers DESC LIMIT ?"
)
CORRELATION_SQL = (
    "SELECT year, price, km_driven, engine_cc, power_bhp FROM offers "  # noqa: S608
    f"WHERE engine_cc IS NOT NULL AND power_bhp IS NOT NULL LIMIT {SAMPLE_LIMIT}"
)
MOVERS_SQL = (
    "SELECT brand, SUM(period >= ?) AS recent, SUM(period < ?) AS early "
    "FROM v_offers GROUP BY brand HAVING early >= 5"
)


def mean(values: list[float]) -> float:
    """Среднее значение."""
    return sum(values) / len(values) if values else 0.0


def deviations(values: list[float]) -> list[float]:
    """Отклонения от среднего."""
    center = mean(values)
    return [value - center for value in values]


def numerator(left: list[float], right: list[float]) -> float:
    """Сумма произведений отклонений."""
    return sum(a * b for a, b in zip(deviations(left), deviations(right), strict=False))


def denominator(left: list[float], right: list[float]) -> float:
    """Корень из произведения сумм квадратов отклонений."""
    return math.sqrt(sum(a * a for a in deviations(left)) * sum(b * b for b in deviations(right)))


def safe_ratio(top: float, bottom: float) -> float:
    """Деление с защитой от нулевого знаменателя."""
    return 0.0 if bottom == 0 else round(top / bottom, 4)


def pearson(pairs: list[tuple[float, float]]) -> float:
    """Коэффициент корреляции Пирсона."""
    left, right = [p[0] for p in pairs], [p[1] for p in pairs]
    return safe_ratio(numerator(left, right), denominator(left, right)) if len(pairs) > 2 else 0.0


def strength(value: float) -> str:
    """Словесная сила связи по модулю коэффициента."""
    return connection_name(abs(value))


def connection_name(magnitude: float) -> str:
    """Название силы связи по модулю коэффициента."""
    thresholds = ((0.75, "сильная"), (0.5, "заметная"), (0.2, "слабая"))
    return next((name for limit, name in thresholds if magnitude >= limit), "нет связи")


def direction(value: float) -> str:
    """Направление связи."""
    return "обратная" if value < 0 else "прямая"


def periods(conn: sqlite3.Connection, months: int = 36) -> list[str]:
    """Список последних периодов витрины."""
    rows = fetch_all(
        conn, "SELECT DISTINCT period FROM v_offers ORDER BY period DESC LIMIT ?", (months,)
    )
    return [row["period"] for row in reversed(rows)]


def monthly_demand(conn: sqlite3.Connection, months: int = 36) -> list[Row]:
    """Объявления и средняя цена по месяцам."""
    return fetch_all(
        conn, "SELECT * FROM v_monthly_demand ORDER BY period DESC LIMIT ?", (months,)
    )[::-1]


def brand_month(conn: sqlite3.Connection) -> list[Row]:
    """Объявления по брендам и месяцам."""
    return fetch_all(conn, "SELECT * FROM v_brand_month ORDER BY period")


def fuel_mix(conn: sqlite3.Connection, months: int = 12) -> list[Row]:
    """Структура топлива по месяцам."""
    return fetch_all(
        conn,
        "SELECT * FROM v_fuel_mix WHERE period >= ? ORDER BY period",
        (boundary(conn, months),),
    )


def boundary(conn: sqlite3.Connection, months: int) -> str:
    """Первый период окна анализа."""
    window = periods(conn, months)
    return window[0] if window else ""


def top_brands(conn: sqlite3.Connection, months: int = 12, limit: int = TOP_BRANDS) -> list[str]:
    """Самые представленные бренды за период."""
    rows = fetch_all(conn, TOP_BRANDS_SQL, (boundary(conn, months), limit))
    return [row["brand"] for row in rows]


def brand_series(conn: sqlite3.Connection, months: int = 12) -> list[dict[str, Any]]:
    """Ряды по брендам: количество объявлений в каждом месяце."""
    rows = brand_month(conn)
    return [series_for(brand, rows) for brand in top_brands(conn, months)]


def series_for(brand: str, rows: list[Row]) -> dict[str, Any]:
    """Ряд одного бренда."""
    own = [row for row in rows if row["brand"] == brand]
    return {"brand": brand, "points": [{"x": row["period"], "y": row["offers"]} for row in own]}


def correlation_pairs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Корреляции цена/пробег/год/мощность на выборке объявлений."""
    rows = fetch_all(conn, CORRELATION_SQL)
    return [
        describe_pair("Пробег → цена", "km_driven", "price", rows),
        describe_pair("Год выпуска → цена", "year", "price", rows),
        describe_pair("Объём двигателя → цена", "engine_cc", "price", rows),
        describe_pair("Мощность → цена", "power_bhp", "price", rows),
        describe_pair("Пробег → год выпуска", "km_driven", "year", rows),
    ]


def describe_pair(title: str, left: str, right: str, rows: list[Row]) -> dict[str, Any]:
    """Корреляция двух числовых колонок с интерпретацией."""
    value = pearson([(float(row[left]), float(row[right])) for row in rows])
    return {
        "pair": title,
        "r": value,
        "strength": strength(value),
        "direction": direction(value),
        "observations": len(rows),
    }


def price_index(conn: sqlite3.Connection, months: int = 36) -> list[dict[str, Any]]:
    """Индекс средней цены: первый период = 100."""
    rows = monthly_demand(conn, months)
    return indexed(rows, "avg_price")


def indexed(rows: list[Row], column: str) -> list[dict[str, Any]]:
    """Нормирует ряд на первый период."""
    base = float(rows[0][column] or 1) if rows else 1.0
    return [
        {"x": row["period"], "y": round(100.0 * float(row[column] or 0) / base, 1)} for row in rows
    ]


def movers(conn: sqlite3.Connection, window: int = MOVERS_WINDOW) -> list[dict[str, Any]]:
    """Рост или падение числа объявлений: последние месяцы против предыдущих."""
    bounds = window_boundaries(conn, window)
    return ranked(fetch_all(conn, MOVERS_SQL, (bounds[0], bounds[0])))


def ranked(rows: list[Row]) -> list[dict[str, Any]]:
    """Сортирует бренды по относительному росту."""
    return sorted([growth_of(row) for row in rows], key=lambda item: item["growth"], reverse=True)


def window_boundaries(conn: sqlite3.Connection, window: int) -> tuple[str, str]:
    """Границы сравнения периодов."""
    return period_head(conn, window), period_head(conn, window * 3)


def period_head(conn: sqlite3.Connection, window: int) -> str:
    """Первый период окна."""
    available = periods(conn, window)
    return available[0] if available else ""


def growth_of(row: Row) -> dict[str, Any]:
    """Относительный рост бренда."""
    early, recent = max(1, int(row["early"] or 0)), int(row["recent"] or 0)
    return {
        "brand": row["brand"],
        "recent": recent,
        "early": int(row["early"] or 0),
        "growth": round(100.0 * (recent - early) / early, 1),
    }


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Сводка для дашборда трендов."""
    return summary_block(monthly_demand(conn, 36), conn)


AVG_PRICE_SQL = "SELECT avg_price FROM v_monthly_demand ORDER BY period DESC LIMIT 1"


def last_average_price(conn: sqlite3.Connection) -> Row:
    """Средняя цена последнего периода."""
    return fetch_one(conn, AVG_PRICE_SQL) or {}


def summary_block(demand: list[Row], conn: sqlite3.Connection) -> dict[str, Any]:
    """Собирает сводку по готовому ряду."""
    return {
        "periods": len(demand),
        "last_period": demand[-1] if demand else {},
        "first_period": demand[0] if demand else {},
        "avg_price_last": last_average_price(conn),
        "top_brands": top_brands(conn, 12),
    }
