"""Аналитика товарной матрицы: ABC по ценности, XYZ по стабильности спроса.

Единица анализа — модель (бренд + модель). Ценность считается по сумме цен
объявлений, стабильность — по коэффициенту вариации числа объявлений в месяц.
Матрица 3×3 даёт готовое решение по каждой ячейке, а не абстрактные цифры.
"""

from __future__ import annotations

import sqlite3
import statistics
from functools import reduce
from itertools import accumulate
from typing import Any

from shared.db import Row, fetch_all, scalar

ABC_LIMITS = (0.80, 0.95)
XYZ_LIMITS = (0.5, 1.0)
CELL_CODES = ("AX", "AY", "AZ", "BX", "BY", "BZ", "CX", "CY", "CZ")

TOTALS_SQL = """
SELECT
    brand,
    model,
    COUNT(*)                        AS offers,
    SUM(price)                      AS value,
    ROUND(AVG(price), 0)            AS avg_price,
    COUNT(DISTINCT period)          AS periods
FROM v_offers
GROUP BY brand, model
ORDER BY value DESC
"""

MONTHLY_SQL = """
SELECT brand, model, period, COUNT(*) AS offers
FROM v_offers
GROUP BY brand, model, period
"""

GAP_SQL = """
SELECT c.brand, c.model, COUNT(c.catalog_id) AS catalog_trims, COALESCE(o.offers, 0) AS offers
FROM catalog_models c
LEFT JOIN (SELECT brand, model, COUNT(*) AS offers FROM offers GROUP BY brand, model) o
       ON o.brand = c.brand AND o.model = c.model
GROUP BY c.brand, c.model
HAVING offers = 0
ORDER BY catalog_trims DESC
LIMIT ?
"""

ORPHAN_SQL = """
SELECT o.brand, o.model, COUNT(*) AS offers
FROM offers o
LEFT JOIN catalog_models c ON c.brand = o.brand AND c.model = o.model
WHERE c.catalog_id IS NULL
GROUP BY o.brand, o.model
ORDER BY offers DESC
LIMIT ?
"""

GAP_COUNT_SQL = """
SELECT COUNT(*) FROM (
    SELECT c.brand, c.model
    FROM catalog_models c
    LEFT JOIN offers o ON o.brand = c.brand AND o.model = c.model
    WHERE o.offer_id IS NULL
    GROUP BY c.brand, c.model
)
"""

ORPHAN_COUNT_SQL = """
SELECT COUNT(DISTINCT o.brand || '|' || o.model)
FROM offers o
LEFT JOIN catalog_models c ON c.brand = o.brand AND c.model = o.model
WHERE c.catalog_id IS NULL
"""

RECOMMENDATIONS = {
    "AX": "Ядро матрицы: держим максимальный контент и наличие, следим за свежестью карточек.",
    "AY": "Стабильная ценность с сезонными колебаниями: планируем промо под спад.",
    "AZ": "Высокая ценность, но рваный спрос: тестируем лоты и точечные акции.",
    "BX": "Рабочая середина: расширяем комплектации, следим за полнотой характеристик.",
    "BY": "Средний приоритет: дополняем описаниями и фото, добираем трафик.",
    "BZ": "Непредсказуемый средний сегмент: проверяем корректность цен и данных.",
    "CX": "Длинный хвост с ровным спросом: оставляем, но без инвестиций в контент.",
    "CY": "Кандидаты на упрощение карточек и объединение комплектаций.",
    "CZ": "Кандидаты на вывод из матрицы: контент не подкреплён спросом.",
}


def coefficient_of_variation(values: list[float]) -> float:
    """Коэффициент вариации: насколько ряд нестабилен."""
    center = statistics.fmean(values) if values else 0.0
    return round(statistics.pstdev(values) / center, 3) if center else 0.0


def abc_class(share: float) -> str:
    """Класс ABC по накопленной доле ценности."""
    return "A" if share <= ABC_LIMITS[0] else "B" if share <= ABC_LIMITS[1] else "C"


def xyz_class(variation: float) -> str:
    """Класс XYZ по стабильности спроса."""
    return "X" if variation <= XYZ_LIMITS[0] else "Y" if variation <= XYZ_LIMITS[1] else "Z"


def append_bucket(
    buckets: dict[tuple[str, str], list[float]],
    row: Row,
) -> dict[tuple[str, str], list[float]]:
    """Добавляет одно наблюдение в словарь по модели."""
    buckets.setdefault((row["brand"], row["model"]), []).append(float(row["offers"]))
    return buckets


def buckets_of(rows: list[Row]) -> dict[tuple[str, str], list[float]]:
    """Складывает месячные значения в словарь по модели."""
    return reduce(append_bucket, rows, {})


def monthly_counts(conn: sqlite3.Connection) -> dict[tuple[str, str], list[float]]:
    """Число объявлений по месяцам для каждой модели."""
    return buckets_of(fetch_all(conn, MONTHLY_SQL))


def with_classes(
    rows: list[Row], buckets: dict[tuple[str, str], list[float]]
) -> list[dict[str, Any]]:
    """Добавляет к моделям классы ABC и XYZ."""
    total = sum(float(row["value"] or 0) for row in rows) or 1.0
    return classify_sequence(rows, buckets, total)


def classified(
    row: Row,
    cumulative: float,
    total: float,
    buckets: dict[tuple[str, str], list[float]],
) -> dict[str, Any]:
    """Дополняет модель долями и классами."""
    variation = coefficient_of_variation(buckets.get((row["brand"], row["model"]), []))
    return matrix_row(row, float(row["value"] or 0) / total, cumulative, variation)


def matrix_row(row: Row, share: float, cumulative: float, variation: float) -> dict[str, Any]:
    """Строка матрицы с классами ABC и XYZ."""
    abc = abc_class(cumulative)
    return {
        **row,
        "share": round(100.0 * share, 2),
        "cumulative": round(100.0 * cumulative, 2),
        "cv": variation,
        "abc": abc,
        "xyz": xyz_class(variation),
        "code": abc + xyz_class(variation),
    }


def shares_of(rows: list[Row], total: float) -> list[float]:
    """Накопленные доли ценности по моделям."""
    return list(accumulate(float(row["value"] or 0) / total for row in rows))


def pairs_of(rows: list[Row], total: float) -> zip[Any]:
    """Пары «строка модели — накопленная доля»."""
    return zip(rows, shares_of(rows, total), strict=False)


def classify_sequence(
    rows: list[Row],
    buckets: dict[tuple[str, str], list[float]],
    total: float,
) -> list[dict[str, Any]]:
    """Последовательно присваивает классы с накоплением доли."""
    rows_with_shares = pairs_of(rows, total)
    return [classified(row, cumulative, total, buckets) for row, cumulative in rows_with_shares]


def model_frame(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Матрица моделей с классами и долями."""
    return with_classes(fetch_all(conn, TOTALS_SQL), monthly_counts(conn))


def models_of(frame: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    """Модели одной ячейки матрицы."""
    return [row for row in frame if row["code"] == code]


def cell_of(frame: list[dict[str, Any]], code: str) -> dict[str, Any]:
    """Агрегат ячейки матрицы."""
    rows = models_of(frame, code)
    return {
        "code": code,
        "models": len(rows),
        "offers": sum(int(row["offers"]) for row in rows),
        "value_mln": round(sum(float(row["value"] or 0) for row in rows) / 1000000.0, 2),
        "examples": [row["model"] for row in rows[:4]],
        "recommendation": RECOMMENDATIONS.get(code, ""),
    }


def cells(frame: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Все девять ячеек матрицы."""
    return [cell_of(frame, code) for code in CELL_CODES]


def distribution(frame: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    """Распределение моделей по классам одной оси."""
    classes = sorted({row[axis] for row in frame})
    return [
        {"label": name, "value": len([row for row in frame if row[axis] == name])}
        for name in classes
    ]


def gaps(conn: sqlite3.Connection, limit: int = 20) -> list[Row]:
    """Позиции каталога без единого объявления."""
    return fetch_all(conn, GAP_SQL, (limit,))


def orphans(conn: sqlite3.Connection, limit: int = 20) -> list[Row]:
    """Объявления без позиции в каталоге."""
    return fetch_all(conn, ORPHAN_SQL, (limit,))


def gap_count(conn: sqlite3.Connection) -> int:
    """Сколько моделей каталога не имеет ни одного объявления."""
    return int(scalar(conn, GAP_COUNT_SQL) or 0)


def orphan_count(conn: sqlite3.Connection) -> int:
    """Сколько моделей с объявлениями отсутствует в каталоге."""
    return int(scalar(conn, ORPHAN_COUNT_SQL) or 0)


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Сводка по матрице для дашборда."""
    frame = model_frame(conn)
    return {
        "models": len(frame),
        "value_mln": round(sum(float(row["value"] or 0) for row in frame) / 1000000.0, 2),
        "abc": distribution(frame, "abc"),
        "xyz": distribution(frame, "xyz"),
        "gaps": gap_count(conn),
        "orphans": orphan_count(conn),
        "top_cells": sorted(cells(frame), key=lambda item: item["value_mln"], reverse=True)[:4],
    }


def focus_list(conn: sqlite3.Connection, code: str = "CZ", limit: int = 15) -> list[dict[str, Any]]:
    """Модели ячейки, требующей решения."""
    return models_of(model_frame(conn), code)[:limit]
