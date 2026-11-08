"""Тесты алертов и итоговой оценки качества."""

from __future__ import annotations

from projects.content_qa import alerts
from projects.content_qa.rules import THRESHOLDS

GOOD = {
    "offers": 100,
    "completeness_pct": 99.0,
    "missing_engine_pct": 0.5,
    "duplicates_pct": 0.1,
    "price_outliers_pct": 0.2,
    "catalog_unmatched_pct": 0.4,
}
BAD = {
    "offers": 100,
    "completeness_pct": 70.0,
    "missing_engine_pct": 12.0,
    "duplicates_pct": 4.0,
    "price_outliers_pct": 6.0,
    "catalog_unmatched_pct": 40.0,
}


def test_no_alerts_for_healthy_metrics():
    assert alerts.build_alerts(GOOD) == []


def test_alerts_fire_for_degraded_metrics():
    codes = {item["code"] for item in alerts.build_alerts(BAD)}
    assert {
        "ALERT-COMPLETENESS",
        "ALERT-ENGINE",
        "ALERT-DUPLICATES",
        "ALERT-PRICE",
        "ALERT-CATALOG",
    } == codes


def test_violated_respects_direction():
    below = next(item for item in THRESHOLDS if item.direction == "below")
    above = next(item for item in THRESHOLDS if item.direction == "above")
    assert alerts.violated(below, below.limit - 1)
    assert not alerts.violated(below, below.limit + 1)
    assert alerts.violated(above, above.limit + 1)
    assert not alerts.violated(above, above.limit - 1)


def test_alert_level_escalates_on_large_deviation():
    threshold = next(item for item in THRESHOLDS if item.code == "ALERT-ENGINE")
    assert alerts.level_of(threshold, threshold.limit * 3) == "bad"
    assert alerts.level_of(threshold, threshold.limit * 1.1) == "warn"


def test_quality_score_is_bounded():
    score = alerts.quality_score(BAD, [{"severity": "bad"}] * 30)
    assert 0.0 <= score <= 100.0


def test_quality_score_rewards_clean_content():
    assert alerts.quality_score(GOOD, []) > alerts.quality_score(BAD, [{"severity": "warn"}] * 10)


def test_alert_object_has_required_fields():
    item = alerts.build_alerts(BAD)[0]
    assert {"level", "code", "title", "detail", "metric", "threshold"} <= set(item)
