"""Пути, константы и настройки проекта."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_CSV = RAW_DIR / "car_details_v3.csv"
WAREHOUSE = DATA_DIR / "warehouse.sqlite"
STATIC_DIR = ROOT / "shared" / "static"
TEMPLATES_DIR = ROOT / "shared" / "templates"

APP_TITLE = "LADA Цифра · Content Analytics"
BRAND = "LADA Цифра"
BRAND_TAGLINE = "Мы создаём цифровое будущее автомобильной индустрии России"
VACANCY = "Junior Content Analyst"

NAV: tuple[tuple[str, str, str], ...] = (
    ("catalog", "Каталог", "/catalog"),
    ("qa", "Качество контента", "/qa"),
    ("trends", "Тренды", "/trends"),
    ("matrix", "Товарная матрица", "/matrix"),
    ("forecast", "Прогноз спроса", "/forecast"),
)

MONTHS_RU = (
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)
