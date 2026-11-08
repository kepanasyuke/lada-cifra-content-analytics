"""Тесты HTTP-слоя каталога: выбор источника и адрес эмулятора."""

from __future__ import annotations

from starlette.requests import Request

from projects.catalog_api.api import source_for, upstream_url
from projects.catalog_api.sources import HttpCatalogSource, LocalCatalogSource


def make_request(port: int = 8123) -> Request:
    """Собирает минимальный ASGI-запрос."""
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "server": ("127.0.0.1", port),
            "root_path": "",
            "path": "/api/catalog/ingest",
            "query_string": b"",
            "headers": [],
        }
    )


def test_upstream_url_uses_current_host():
    assert upstream_url(make_request(8000)) == "http://127.0.0.1:8000/upstream"


def test_upstream_url_has_no_double_slash():
    assert "//upstream" not in upstream_url(make_request(9000)).replace("http://", "")


def test_live_mode_builds_http_source(conn):
    source = source_for(conn, "live", "http://127.0.0.1:9000/upstream")
    assert isinstance(source, HttpCatalogSource)
    assert source.base_url == "http://127.0.0.1:9000/upstream"


def test_local_mode_builds_warehouse_source(conn):
    source = source_for(conn, "local", "http://127.0.0.1:9000/upstream")
    assert isinstance(source, LocalCatalogSource)


def test_unknown_mode_falls_back_to_local(conn):
    assert isinstance(source_for(conn, "что-то", "http://x/upstream"), LocalCatalogSource)
