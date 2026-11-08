"""Парсер HTML-каталога: карточки характеристик -> записи каталога.

Модуль не привязан к конкретному сайту: селекторы вынесены в константы,
поэтому под новый источник правится карта полей, а не логика.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

CARD_SELECTOR = "[data-spec-card]"
FIELD_SELECTORS = {
    "brand": "[data-spec='brand']",
    "model": "[data-spec='model']",
    "trim": "[data-spec='trim']",
    "fuel": "[data-spec='fuel']",
    "transmission": "[data-spec='transmission']",
}
NUMBER_SELECTORS = {
    "engine_cc": "[data-spec='engine']",
    "power_bhp": "[data-spec='power']",
    "seats": "[data-spec='seats']",
    "year_from": "[data-spec='year']",
}
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def soup_of(html: str) -> BeautifulSoup:
    """Разбирает HTML документ."""
    return BeautifulSoup(html, "html.parser")


def text_of(node: Tag, selector: str) -> str:
    """Текст первого совпадения или пустая строка."""
    found = node.select_one(selector)
    return " ".join(found.get_text(" ", strip=True).split()) if found else ""


def compact(text: str) -> str:
    """Убирает разделители разрядов и меняет запятую на точку."""
    return text.replace("\u00a0", "").replace(" ", "").replace(",", ".")


def number_of(node: Tag, selector: str) -> float | None:
    """Первое число из элемента или None."""
    match = NUMBER_PATTERN.search(compact(text_of(node, selector)))
    return float(match.group()) if match else None


def as_int(value: float | None) -> int | None:
    """Округляет число до целого."""
    return None if value is None else round(value)


def card_to_item(card: Tag) -> dict[str, Any]:
    """Извлекает поля позиции каталога из карточки."""
    return {
        **{name: text_of(card, selector) for name, selector in FIELD_SELECTORS.items()},
        "engine_cc": as_int(number_of(card, NUMBER_SELECTORS["engine_cc"])),
        "power_bhp": number_of(card, NUMBER_SELECTORS["power_bhp"]),
        "seats": as_int(number_of(card, NUMBER_SELECTORS["seats"])),
        "year_from": as_int(number_of(card, NUMBER_SELECTORS["year_from"])),
        "year_to": None,
        "offers": 1,
    }


def parse_spec_cards(html: str) -> list[dict[str, Any]]:
    """Разбирает все карточки характеристик страницы."""
    return [card_to_item(card) for card in soup_of(html).select(CARD_SELECTOR)]


def is_complete(item: dict[str, Any]) -> bool:
    """Позиция содержит обязательные поля каталога."""
    required = ("brand", "model", "fuel", "transmission")
    return all(item.get(name) for name in required)


def split_complete(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Делит позиции на полные и неполные."""
    complete = [item for item in items if is_complete(item)]
    return complete, [item for item in items if not is_complete(item)]
