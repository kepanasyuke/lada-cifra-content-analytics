"""Тесты единого приложения: маршруты, редирект, health-проверка."""

from __future__ import annotations

from fastapi.responses import RedirectResponse
from starlette.routing import Mount

import app as application
from shared.config import APP_TITLE


def route_paths() -> list[str]:
    """Пути всех маршрутов из схемы OpenAPI."""
    return sorted(application.app.openapi()["paths"])


def test_app_title_matches_config():
    assert application.app.title == APP_TITLE


def test_root_redirects_to_catalog():
    response = application.index()
    assert isinstance(response, RedirectResponse)
    assert response.headers["location"] == "/catalog"


def test_health_route_is_registered():
    assert "/health" in route_paths()


def test_every_project_page_is_registered():
    assert {"/catalog", "/qa", "/trends", "/matrix", "/forecast"} <= set(route_paths())


def test_every_project_api_is_registered():
    api_paths = {path for path in route_paths() if path.startswith("/api/")}
    assert {"/api/catalog/summary", "/api/qa/summary", "/api/trends/summary"} <= api_paths
    assert {"/api/matrix/summary", "/api/forecast/summary"} <= api_paths


def test_upstream_emulator_is_mounted():
    assert {"/upstream/v1/catalog", "/upstream/v1/catalog/total"} <= set(route_paths())


def test_router_count_matches_projects():
    assert len(application.ROUTERS) == 6
    assert len(application.ROUTERS) - 1 == 5


def test_static_files_are_mounted():
    mounts = [route for route in application.app.routes if isinstance(route, Mount)]
    assert any(route.path == "/static" for route in mounts)


def test_report_mentions_project_count():
    report = application.report_of(8128, 2058)
    assert report["status"] == "ok"
    assert report["offers"] == 8128
    assert report["catalog"] == 2058
    assert report["projects"] == 5
    assert report["environment"]


def test_counts_reads_warehouse(conn):
    assert application.counts(conn)["offers"] == 6


def test_counts_reports_empty_catalog(conn):
    assert application.counts(conn)["catalog"] == 0


def test_with_connection_closes_connection(monkeypatch):
    warehouse = _FakeWarehouse()
    monkeypatch.setattr(application, "connect", lambda: warehouse)
    assert application.with_connection(application.counts)["status"] == "ok"
    assert warehouse.closed is True


def test_with_connection_returns_counts(monkeypatch):
    monkeypatch.setattr(application, "connect", lambda: _FakeWarehouse(offers=7))
    assert application.with_connection(application.counts)["offers"] == 7


def test_health_reports_ok(monkeypatch):
    monkeypatch.setattr(application, "connect", lambda: _FakeWarehouse())
    assert application.health()["status"] == "ok"


class _FakeWarehouse:
    """Соединение-заглушка для health-проверки без витрины."""

    def __init__(self, offers: int = 0) -> None:
        self.offers = offers
        self.closed = False

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return (self.offers,)

    def close(self) -> None:
        self.closed = True
