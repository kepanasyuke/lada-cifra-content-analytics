"""Тесты клиента внешнего каталога и локального источника."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from projects.catalog_api import sources
from projects.catalog_api.sources import (
    CatalogUnavailableError,
    HttpCatalogSource,
    LocalCatalogSource,
)

PAYLOAD = {
    "page": 1,
    "pages": 2,
    "total": 3,
    "items": [{"brand": "LADA", "model": "Vesta", "trim": "Comfort"}],
}


class FakeResponse:
    """Поддельный ответ requests."""

    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.payload = payload
        self.status_code = status
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_http_source_converts_payload_to_page(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: FakeResponse(PAYLOAD))
    page = HttpCatalogSource().page(1)
    assert page.total == 3
    assert page.pages == 2
    assert page.items[0]["model"] == "Vesta"


def test_http_source_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def flaky(*_args: Any, **_kwargs: Any):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.ConnectionError("нет сети")
        return FakeResponse(PAYLOAD)

    monkeypatch.setattr(requests, "get", flaky)
    monkeypatch.setattr(sources.time, "sleep", lambda *_args: None)
    assert HttpCatalogSource(retries=3).page(1).total == 3
    assert calls["count"] == 2


def test_http_source_raises_after_all_retries(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: FakeResponse({}, status=500))
    monkeypatch.setattr(sources.time, "sleep", lambda *_args: None)
    with pytest.raises(CatalogUnavailableError):
        HttpCatalogSource(retries=2).page(1)


def test_local_source_returns_same_shape(conn):
    page = LocalCatalogSource(conn).page(1)
    assert page.total == 5
    assert page.pages == 1
    assert {"brand", "model", "trim", "id"} <= set(page.items[0])


def test_pagination_splits_catalog(conn):
    page = LocalCatalogSource(conn, page_size=2).page(2)
    assert page.number == 2
    assert page.pages == 3
    assert len(page.items) == 2
