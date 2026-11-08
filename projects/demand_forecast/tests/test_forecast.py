"""Тесты прогноза потребности."""

from __future__ import annotations

from projects.demand_forecast import forecast

FLAT = [10.0] * 24
GROWING = [float(100 + 5 * index) for index in range(24)]
SEASONAL = [float(100 + 30 * ((index % 12) in (2, 3, 9))) for index in range(36)]


def test_next_period_rolls_over_year():
    assert forecast.next_period("2026-11", 1) == "2026-12"
    assert forecast.next_period("2026-12", 1) == "2027-01"
    assert forecast.next_period("2026-01", 12) == "2027-01"


def test_initial_state_uses_two_seasons():
    state = forecast.initial_state(FLAT)
    assert state.level == 10.0
    assert state.trend == 0.0
    assert len(state.season) == 12


def test_smoothing_keeps_flat_series_flat():
    points = forecast.project(forecast.smooth(FLAT), 0, 6)
    assert all(round(point, 2) == 10.0 for point in points)


def test_trend_follows_growing_series():
    points = forecast.project(forecast.smooth(GROWING), 0, 3)
    assert points[0] < points[1] < points[2]
    assert points[0] > forecast.initial_state(GROWING).level


def test_forecast_is_not_negative():
    assert all(point >= 0 for point in forecast.project(forecast.smooth([0.0] * 24), 0, 6))


def test_seasonal_pattern_repeats():
    points = forecast.project(forecast.smooth(SEASONAL), 0, 14)
    assert round(points[2], 1) > round(points[0], 1)


def test_fitted_and_residuals_have_history_length():
    assert len(forecast.fitted(SEASONAL)) == len(SEASONAL)
    assert len(forecast.residuals(SEASONAL)) == len(SEASONAL)


NOISY = [float(100 + 30 * ((index % 12) in (2, 3, 9)) + (index % 7) * 5) for index in range(36)]


def test_sigma_is_zero_for_perfect_pattern():
    assert forecast.sigma(SEASONAL) == 0.0


def test_sigma_is_positive_for_noisy_series():
    assert forecast.sigma(NOISY) > 0


def test_mape_zero_for_ideal_forecast():
    assert forecast.mape([10.0, 20.0], [10.0, 20.0]) == 0.0
    assert forecast.mape([], []) == 0.0


def test_backtest_returns_mape_and_horizon():
    report = forecast.backtest(SEASONAL, 6)
    assert report["horizon"] == 6
    assert report["mape"] >= 0
    assert len(report["actual"]) == len(report["predicted"]) == 6


def test_forecast_points_carry_band():
    points = forecast.forecast_points("2026-01", [10.0, 12.0], 2.0)
    assert points[0]["x"] == "2026-02"
    assert points[0]["low"] <= points[0]["y"] <= points[0]["high"]


def test_plan_converts_units_to_budget():
    plan = forecast.plan_of([{"y": 100.0}, {"y": 200.0}], 500000.0)
    assert plan["units"] == 300
    assert plan["budget_mln"] == 150.0


def test_forecast_on_warehouse(conn):
    data = forecast.forecast(conn, 6)
    assert len(data["forecast"]) == 6
    assert data["history"]
    assert data["plan"]["months"] == 6


def test_summary_exposes_quality_and_plan(conn):
    data = forecast.summary(conn)
    assert {"mape", "sigma", "history_months", "plan", "next_months"} <= set(data)
