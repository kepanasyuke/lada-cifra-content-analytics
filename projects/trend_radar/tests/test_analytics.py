"""Тесты аналитики трендов."""

from __future__ import annotations

from projects.trend_radar import analytics


def test_mean_and_deviations():
    assert analytics.mean([2.0, 4.0]) == 3.0
    assert analytics.mean([]) == 0.0
    assert analytics.deviations([1.0, 3.0]) == [-1.0, 1.0]


def test_pearson_is_one_for_linear_series():
    assert analytics.pearson([(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]) == 1.0


def test_pearson_is_minus_one_for_inverse_series():
    assert analytics.pearson([(1.0, 6.0), (2.0, 4.0), (3.0, 2.0)]) == -1.0


def test_pearson_is_zero_for_short_or_flat_series():
    assert analytics.pearson([(1.0, 1.0), (2.0, 2.0)]) == 0.0
    assert analytics.pearson([(1.0, 5.0), (2.0, 5.0), (3.0, 5.0)]) == 0.0


def test_strength_buckets():
    assert analytics.strength(0.9) == "сильная"
    assert analytics.strength(-0.6) == "заметная"
    assert analytics.strength(0.3) == "слабая"
    assert analytics.strength(0.05) == "нет связи"


def test_direction_of_correlation():
    assert analytics.direction(-0.4) == "обратная"
    assert analytics.direction(0.4) == "прямая"


def test_monthly_demand_sorted_ascending(conn):
    rows = analytics.monthly_demand(conn, 36)
    assert [row["period"] for row in rows] == sorted(row["period"] for row in rows)


def test_price_index_starts_at_100(conn):
    index = analytics.price_index(conn, 36)
    assert index[0]["y"] == 100.0


def test_brand_series_grouped_by_brand(conn):
    series = analytics.brand_series(conn, 36)
    assert series
    assert all(item["brand"] for item in series)


def test_correlation_pairs_have_interpretation(conn):
    pairs = analytics.correlation_pairs(conn)
    assert len(pairs) == 5
    assert all(
        {"pair", "r", "strength", "direction", "observations"} <= set(item) for item in pairs
    )


def test_movers_sorted_by_growth(conn):
    items = analytics.movers(conn)
    growth = [item["growth"] for item in items]
    assert growth == sorted(growth, reverse=True)


def test_summary_has_periods_and_last_period(conn):
    summary = analytics.summary(conn)
    assert summary["periods"] >= 1
    assert "period" in summary["last_period"]
