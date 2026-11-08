"""Источники внешнего каталога: живой HTTP-API и локальная реализация."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import requests

from projects.catalog_api.upstream import catalog_payload

DEFAULT_BASE_URL = "http://127.0.0.1:8000/upstream"
DEFAULT_PAGE_SIZE = 500
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3
BACKOFF_BASE = 0.25


class CatalogUnavailableError(RuntimeError):
    """Внешний каталог недоступен после всех попыток."""


@dataclass(frozen=True)
class CatalogPage:
    """Страница ответа внешнего каталога."""

    number: int
    pages: int
    total: int
    items: list[dict[str, Any]]


class CatalogSource(Protocol):
    """Контракт источника каталога."""

    def page(self, number: int) -> CatalogPage:
        """Возвращает страницу каталога."""
        ...


@dataclass(frozen=True)
class HttpCatalogSource:
    """Клиент реального HTTP-API внешнего каталога."""

    base_url: str = DEFAULT_BASE_URL
    page_size: int = DEFAULT_PAGE_SIZE
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES

    def url(self) -> str:
        """Адрес метода выдачи каталога."""
        return f"{self.base_url.rstrip('/')}/v1/catalog"

    def params(self, number: int) -> dict[str, int]:
        """Параметры пагинации."""
        return {"page": number, "page_size": self.page_size}

    def page(self, number: int) -> CatalogPage:
        """Забирает страницу каталога по HTTP."""
        payload = fetch_json(self.url(), self.params(number), self.timeout, self.retries)
        return to_page(payload)


@dataclass
class LocalCatalogSource:
    """Тот же контракт, но данные отдаются из витрины без сети."""

    conn: sqlite3.Connection
    page_size: int = DEFAULT_PAGE_SIZE

    def page(self, number: int) -> CatalogPage:
        """Страница каталога из локальной витрины."""
        return to_page(catalog_payload(self.conn, number, self.page_size))


def to_page(payload: dict[str, Any]) -> CatalogPage:
    """Преобразует JSON ответа в CatalogPage."""
    return CatalogPage(
        int(payload["page"]),
        int(payload["pages"]),
        int(payload["total"]),
        list(payload["items"]),
    )


def checked_json(response: requests.Response) -> dict[str, Any]:
    """Проверяет статус ответа и отдаёт JSON."""
    response.raise_for_status()
    return dict(response.json())


def fetch_json(
    url: str,
    params: dict[str, int],
    timeout: float,
    retries: int = DEFAULT_RETRIES,
) -> dict[str, Any]:
    """GET с повторами и нарастающей паузой."""
    return retry(lambda: checked_json(requests.get(url, params=params, timeout=timeout)), retries)


def retry(action: Callable[[], dict[str, Any]], retries: int) -> dict[str, Any]:
    """Повторяет действие при сетевой ошибке."""
    for attempt in range(retries):
        try:
            return action()
        except requests.RequestException:
            pause_or_raise(attempt, retries)
    raise CatalogUnavailableError("каталог недоступен")


def pause_or_raise(attempt: int, retries: int) -> None:
    """Пауза перед следующей попыткой или проброс ошибки."""
    if attempt + 1 == retries:
        raise CatalogUnavailableError("каталог недоступен после повторов")
    time.sleep(BACKOFF_BASE * (attempt + 1))


def later_pages(source: CatalogSource, pages: int) -> list[CatalogPage]:
    """Страницы со второй по последнюю."""
    return [source.page(number) for number in range(2, pages + 1)]


def fetch_catalog(source: CatalogSource) -> list[CatalogPage]:
    """Забирает все страницы каталога."""
    first = source.page(1)
    return [first, *later_pages(source, first.pages)]


def source_name(source: CatalogSource) -> str:
    """Человекочитаемое имя источника для журнала запусков."""
    return getattr(source, "base_url", "local-warehouse")
