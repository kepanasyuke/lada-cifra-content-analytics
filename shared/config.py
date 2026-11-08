"""Пути, константы и настройки проекта.

Значения по умолчанию рассчитаны на локальный запуск из репозитория, но пути
и режим можно переопределить переменными окружения — так приложение одинаково
работает и в контейнере, и на машине разработчика.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env_text(name: str, fallback: str) -> str:
    """Строковая настройка из переменной окружения."""
    return os.environ.get(name) or fallback


def env_path(name: str, fallback: Path) -> Path:
    """Путь из переменной окружения или значение по умолчанию."""
    return Path(os.environ.get(name) or fallback)


DATA_DIR = env_path("LADA_DATA_DIR", ROOT / "data")
RAW_DIR = DATA_DIR / "raw"
RAW_CSV = env_path("LADA_CSV", RAW_DIR / "car_details_v3.csv")
WAREHOUSE = env_path("LADA_WAREHOUSE", DATA_DIR / "warehouse.sqlite")
STATIC_DIR = ROOT / "shared" / "static"
TEMPLATES_DIR = ROOT / "shared" / "templates"

ENVIRONMENT = env_text("LADA_ENV", "dev")
LOG_LEVEL = env_text("LADA_LOG_LEVEL", "INFO").upper()
HOST = env_text("LADA_HOST", "127.0.0.1")
PORT = int(env_text("LADA_PORT", "8000"))
WORKERS = int(env_text("LADA_WORKERS", "1"))

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
