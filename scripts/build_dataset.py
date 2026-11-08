"""Сборка витрины данных: сырой CSV внешнего рынка -> SQLite-хранилище.

Запуск: python -m scripts.build_dataset
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from datetime import date, timedelta
from itertools import accumulate
from pathlib import Path
from typing import Any

from shared.config import RAW_CSV, ROOT, WAREHOUSE
from shared.db import DictConnection, connect, executemany, fetch_one

SCHEMA_SQL = ROOT / "sql" / "schema.sql"
VIEWS_SQL = ROOT / "sql" / "views.sql"

MULTIWORD_BRANDS = ("Mercedes-Benz", "Land Rover", "Ashok Leyland", "Maruti Suzuki", "Force Motors")
MODEL_ALIASES = {
    ("Maruti", "Wagon"): "Wagon R",
    ("Maruti", "Vitara"): "Vitara Brezza",
    ("Hyundai", "Grand"): "Grand i10",
    ("Hyundai", "Elite"): "Elite i20",
}
SEASONALITY = (0.07, 0.07, 0.09, 0.10, 0.09, 0.08, 0.07, 0.08, 0.10, 0.09, 0.08, 0.08)
TIMELINE_START = date(2023, 1, 1)
TIMELINE_MONTHS = 36
GROWTH_PER_MONTH = 0.012
SOURCE_NAME = "cardekho_public_csv"

COLUMNS = (
    "offer_id",
    "source",
    "name",
    "brand",
    "model",
    "trim",
    "year",
    "price",
    "currency",
    "km_driven",
    "fuel",
    "seller",
    "transmission",
    "owner",
    "mileage_kmpl",
    "engine_cc",
    "power_bhp",
    "torque",
    "seats",
    "listed_at",
    "listed_at_source",
)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
INSERT_SQL = f"INSERT INTO offers ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})"  # noqa: S608


def read_rows(path: Path = RAW_CSV) -> list[dict[str, str]]:
    """Читает сырой CSV в список словарей."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_number(raw: str) -> float | None:
    """Достаёт число из строки вида «1248 CC» или «74.5 bhp»."""
    digits = "".join(char if char.isdigit() or char == "." else " " for char in raw or "").split()
    return float(digits[0]) if digits else None


def to_int(raw: str) -> int | None:
    """Целое число из строки."""
    value = to_number(raw)
    return None if value is None else int(value)


def normalize_text(raw: str | None) -> str:
    """Чистит строковое поле."""
    return " ".join((raw or "").split())


def is_prefix(tokens: list[str], brand: str) -> bool:
    """Совпадает ли начало названия с составным брендом."""
    size = len(brand.split())
    return " ".join(tokens[:size]) == brand


def match_multiword(tokens: list[str]) -> str:
    """Ищет составной бренд в начале названия."""
    return next((item for item in MULTIWORD_BRANDS if is_prefix(tokens, item)), "")


def multiword_part(tokens: list[str], brand: str) -> tuple[str, str, str]:
    """Разбирает название с составным брендом."""
    size = len(brand.split())
    return brand, tokens[size] if len(tokens) > size else "", " ".join(tokens[size + 1 :])


def plain_part(tokens: list[str]) -> tuple[str, str, str]:
    """Разбирает название с однословным брендом."""
    return tokens[0], tokens[1] if len(tokens) > 1 else "", " ".join(tokens[2:])


def brand_and_rest(tokens: list[str]) -> tuple[str, str, str]:
    """Определяет бренд, головное слово модели и остаток названия."""
    brand = match_multiword(tokens)
    return multiword_part(tokens, brand) if brand else plain_part(tokens)


def resolve_model(brand: str, head: str, rest: str) -> tuple[str, str]:
    """Уточняет модель по таблице псевдонимов."""
    return MODEL_ALIASES.get((brand, head), head), rest


def model_of(brand: str, head: str, rest: str) -> tuple[str, str, str]:
    """Собирает тройку бренд-модель-комплектация."""
    model, trim = resolve_model(brand, head, rest)
    return brand, model, trim


def parse_brand_model(name: str) -> tuple[str, str, str]:
    """Возвращает бренд, модель и комплектацию объявления."""
    return model_of(*brand_and_rest(normalize_text(name).split(" ")))


def month_weight(index: int) -> float:
    """Вес месяца: сезонность плюс медленный рост рынка."""
    return SEASONALITY[index % 12] * (1 + GROWTH_PER_MONTH * index)


def listing_weights() -> list[float]:
    """Веса месяцев таймлайна."""
    return [month_weight(index) for index in range(TIMELINE_MONTHS)]


def hash_share(seed: str) -> float:
    """Детерминированное число в диапазоне [0, 1) из строки."""
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def cumulative_index(weights: list[float], target: float) -> int:
    """Индекс, на котором накопленная сумма весов превышает цель."""
    edges = list(accumulate(weights))
    return next((index for index, edge in enumerate(edges) if target <= edge), len(weights) - 1)


def pick_month(seed: str) -> int:
    """Детерминированно выбирает месяц таймлайна для объявления."""
    weights = listing_weights()
    return cumulative_index(weights, hash_share(seed) * sum(weights))


def month_start(index: int) -> date:
    """Дата начала месяца из индекса таймлайна."""
    years, month = divmod(TIMELINE_START.month - 1 + index, 12)
    return date(TIMELINE_START.year + years, month + 1, 1)


def day_offset(name: str) -> int:
    """День внутри месяца, тоже детерминированный."""
    return 1 + int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:2], 16) % 27


def simulated_listing_date(name: str, year: str, price: str) -> str:
    """Псевдо-дата публикации объявления (детерминированная, для таймлайна)."""
    month_index = pick_month(f"{name}|{year}|{price}")
    return (month_start(month_index) + timedelta(days=day_offset(name) - 1)).isoformat()


def identity_fields(row: dict[str, str], offer_id: int) -> dict[str, Any]:
    """Идентификация и классификация объявления."""
    brand, model, trim = parse_brand_model(row["name"])
    return {
        "offer_id": offer_id,
        "source": SOURCE_NAME,
        "name": normalize_text(row["name"]),
        "brand": brand,
        "model": model,
        "trim": trim,
    }


def market_fields(row: dict[str, str]) -> dict[str, Any]:
    """Рыночные условия сделки."""
    return {
        "year": to_int(row["year"]) or 0,
        "price": to_int(row["selling_price"]) or 0,
        "currency": "INR",
        "km_driven": to_int(row["km_driven"]) or 0,
        "fuel": normalize_text(row["fuel"]),
        "seller": normalize_text(row["seller_type"]),
        "transmission": normalize_text(row["transmission"]),
        "owner": normalize_text(row["owner"]),
    }


def spec_fields(row: dict[str, str]) -> dict[str, Any]:
    """Технические характеристики карточки."""
    return {
        "mileage_kmpl": to_number(row["mileage"]),
        "engine_cc": to_int(row["engine"]),
        "power_bhp": to_number(row["max_power"]),
        "torque": normalize_text(row["torque"]) or None,
        "seats": to_int(row["seats"]),
    }


def listing_fields(row: dict[str, str]) -> dict[str, Any]:
    """Таймлайн публикации."""
    return {
        "listed_at": simulated_listing_date(row["name"], row["year"], row["selling_price"]),
        "listed_at_source": "simulated",
    }


def normalize(row: dict[str, str], offer_id: int) -> dict[str, Any]:
    """Приводит строку CSV к записи таблицы offers."""
    return {
        **identity_fields(row, offer_id),
        **market_fields(row),
        **spec_fields(row),
        **listing_fields(row),
    }


def offer_tuple(offer: dict[str, Any]) -> tuple[Any, ...]:
    """Кортеж значений в порядке колонок."""
    return tuple(offer[column] for column in COLUMNS)


def apply_schema(conn: DictConnection) -> DictConnection:
    """Создаёт таблицы."""
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return conn


def apply_views(conn: DictConnection) -> DictConnection:
    """Создаёт аналитические вьюхи."""
    conn.executescript(VIEWS_SQL.read_text(encoding="utf-8"))
    return conn


def init_db(path: Path) -> DictConnection:
    """Создаёт пустую базу со схемой и вьюхами."""
    return apply_views(apply_schema(connect(path)))


def fresh_db(path: Path) -> DictConnection:
    """Пересоздаёт базу с нуля."""
    Path(path).unlink(missing_ok=True)
    return init_db(path)


def load_offers(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> int:
    """Загружает объявления в хранилище."""
    offers = [offer_tuple(normalize(row, index)) for index, row in enumerate(rows, start=1)]
    return executemany(conn, INSERT_SQL, offers)


def load_views(conn: sqlite3.Connection) -> None:
    """Пересоздаёт аналитические вьюхи."""
    conn.executescript(VIEWS_SQL.read_text(encoding="utf-8"))


def rebuild(path: Path = WAREHOUSE, raw: Path = RAW_CSV) -> int:
    """Полная пересборка витрины."""
    return load_offers(fresh_db(path), read_rows(raw))


def stats(path: Path = WAREHOUSE) -> dict[str, Any]:
    """Короткая сводка по собранной витрине."""
    query = "SELECT COUNT(*) AS offers, COUNT(DISTINCT brand) AS brands FROM offers"
    return fetch_one(connect(path), query) or {}


def summary_line() -> str:
    """Текст итогового отчёта сборки."""
    return f"витрина: {WAREHOUSE}\nзагружено объявлений: {rebuild()}\nитог: {stats()}"


def main() -> None:
    """Точка входа CLI."""
    print(summary_line())


if __name__ == "__main__":
    main()
