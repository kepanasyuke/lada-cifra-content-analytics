"""Тесты ингеста каталога и выборок сервиса."""

from __future__ import annotations

from projects.catalog_api import service
from projects.catalog_api.sources import LocalCatalogSource


def test_ingest_writes_catalog_positions(conn):
    report = service.ingest(conn, LocalCatalogSource(conn))
    assert report["records"] == 5
    assert report["pages"] == 1
    assert service.catalog_size(conn) == 5


def test_ingest_is_idempotent(conn):
    service.ingest(conn, LocalCatalogSource(conn))
    service.ingest(conn, LocalCatalogSource(conn))
    assert service.catalog_size(conn) == 5


def test_ingest_logs_run(conn):
    report = service.ingest(conn, LocalCatalogSource(conn))
    runs = service.runs(conn)
    assert runs[0]["run_id"] == report["run_id"]
    assert runs[0]["status"] == "ok"


def test_summary_counts_brands_and_models(conn):
    service.ingest(conn, LocalCatalogSource(conn))
    summary = service.summary(conn)
    assert summary["brands"] == 1
    assert summary["models"] == 4


def test_search_models_filters_by_query(conn):
    service.ingest(conn, LocalCatalogSource(conn))
    found = service.search_models(conn, query="sw")
    assert [item["model"] for item in found] == ["Vesta"]


AURA_SQL = (
    "INSERT INTO catalog_models (brand, model, trim, fuel, transmission, updated_at) "
    "VALUES ('LADA', 'Aura', 'Comfort', 'бензин', 'автомат', '2026-01-01')"
)


def test_coverage_shows_positions_without_offers(conn):
    conn.execute(AURA_SQL)
    rows = service.coverage(conn)
    aura = next(item for item in rows if item["model"] == "Aura")
    assert aura["offers"] == 0
    assert aura["catalog_trims"] == 1
