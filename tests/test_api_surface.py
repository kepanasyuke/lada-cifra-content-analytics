"""Тесты HTTP-слоя пяти проектов: ответы эндпоинтов на тестовой витрине."""

from __future__ import annotations

from projects.catalog_api import api as catalog_api
from projects.catalog_api import service as catalog_service
from projects.catalog_api.sources import LocalCatalogSource
from projects.content_qa import api as qa_api
from projects.demand_forecast import api as forecast_api
from projects.matrix_optimizer import api as matrix_api
from projects.trend_radar import api as trends_api


def filled_catalog(conn):
    """Загружает каталог из витрины и возвращает отчёт."""
    return catalog_service.ingest(conn, LocalCatalogSource(conn))


def test_catalog_summary_shape(conn):
    summary = catalog_api.catalog_summary(conn=conn)
    assert set(summary) >= {"trims", "brands", "models", "last_run"}


def test_catalog_models_filters_and_limit(conn):
    filled_catalog(conn)
    rows = catalog_api.catalog_models(brand="LADA", q="vesta", limit=1, conn=conn)
    assert len(rows) == 1
    assert rows[0]["model"] == "Vesta"


def test_catalog_brands_counts_positions(conn):
    filled_catalog(conn)
    brands = catalog_api.catalog_brands(conn=conn)
    assert brands[0]["brand"] == "LADA"
    assert brands[0]["models"] == 4


def test_catalog_runs_after_ingest(conn):
    filled_catalog(conn)
    runs = catalog_api.catalog_runs(conn=conn)
    assert runs[0]["status"] == "ok"
    assert runs[0]["source"] == "local-warehouse"


def test_qa_run_persists_findings(conn):
    report = qa_api.qa_run(conn=conn)
    assert report["run_id"] == 1
    assert report["findings"] > 0


def test_qa_findings_filter_by_code(conn):
    qa_api.qa_run(conn=conn)
    rows = qa_api.qa_findings(code="QA-CATALOG-MISS", limit=50, conn=conn)
    assert rows
    assert {row["rule_code"] for row in rows} == {"QA-CATALOG-MISS"}


def test_qa_alerts_carry_levels(conn):
    qa_api.qa_run(conn=conn)
    alerts = qa_api.qa_alerts(conn=conn)
    assert alerts
    assert {alert["level"] for alert in alerts} <= {"bad", "warn"}


def test_trends_demand_pairs_series_with_index(conn):
    data = trends_api.trends_demand(months=36, conn=conn)
    assert data["demand"]
    assert data["index"][0]["y"] == 100.0


def test_trends_brands_returns_series(conn):
    series = trends_api.trends_brands(months=36, conn=conn)
    assert series
    assert all({"brand", "points"} <= set(item) for item in series)


def test_trends_fuel_shares_sum_to_hundred(conn):
    rows = trends_api.trends_fuel(months=36, conn=conn)
    assert rows
    totals = {}
    for row in rows:
        totals[row["period"]] = totals.get(row["period"], 0.0) + row["share_pct"]
    assert all(round(value) == 100 for value in totals.values())


def test_trends_correlations_are_interpreted(conn):
    pairs = trends_api.trends_correlations(conn=conn)
    assert len(pairs) == 5
    assert all(-1.0 <= item["r"] <= 1.0 for item in pairs)


def test_matrix_cells_cover_nine_codes(conn):
    cells = matrix_api.matrix_cells(conn=conn)
    assert [cell["code"] for cell in cells] == list(matrix_api.matrix.CELL_CODES)


def test_matrix_models_filter_by_code(conn):
    rows = matrix_api.matrix_models(code="AX", limit=10, conn=conn)
    assert all(row["code"] == "AX" for row in rows)


def test_matrix_gaps_and_orphans(conn):
    assert matrix_api.matrix_gaps(limit=5, conn=conn) == []
    assert len(matrix_api.matrix_orphans(limit=5, conn=conn)) >= 1


def test_forecast_series_respects_horizon(conn):
    data = forecast_api.forecast_series(horizon=3, conn=conn)
    assert len(data["forecast"]) == 3
    assert data["history"]


def test_forecast_backtest_uses_horizon(conn):
    report = forecast_api.forecast_backtest(horizon=2, conn=conn)
    assert report["horizon"] == 2
    assert report["mape"] >= 0


def test_forecast_summary_has_plan(conn):
    data = forecast_api.forecast_summary(conn=conn)
    assert data["plan"]["months"] >= 1
    assert data["history_months"] >= 1


def test_project_pages_render(request_factory):
    pages = (
        (catalog_api.catalog_page, "/catalog"),
        (qa_api.qa_page, "/qa"),
        (trends_api.trends_page, "/trends"),
        (matrix_api.matrix_page, "/matrix"),
        (forecast_api.forecast_page, "/forecast"),
    )
    for handler, path in pages:
        assert handler(request_factory(path)).status_code == 200
