"""Тесты правил качества контента."""

from __future__ import annotations

from projects.content_qa import checks
from projects.content_qa.rules import FIELD_RULES, SEVERITY_WEIGHT, THRESHOLDS


def test_field_rules_cover_all_optional_fields():
    assert len(FIELD_RULES) == 5
    assert {rule.severity for rule in FIELD_RULES} <= set(SEVERITY_WEIGHT)


def test_missing_engine_is_detected(conn):
    codes = [item["rule_code"] for item in checks.field_findings(conn, FIELD_RULES[0])]
    assert codes == ["QA-FUEL-ENGINE"]


def test_missing_seats_detected(conn):
    findings = checks.field_findings(conn, FIELD_RULES[3])
    assert len(findings) == 1
    assert findings[0]["offer_id"] == 4


def test_price_outlier_below_floor(edge_conn):
    findings = checks.price_findings(edge_conn)
    assert any("3000" in item["message"] for item in findings)


def test_price_bounds_are_ordered(conn):
    low, high = checks.price_bounds(conn)
    assert low < high


COPY_OFFER_SQL = (
    "INSERT INTO offers (offer_id, source, name, brand, model, trim, year, price, currency, "
    "km_driven, fuel, seller, transmission, owner, listed_at, listed_at_source) "
    "SELECT offer_id + 100, source, name, brand, model, trim, year, price, currency, "
    "km_driven, fuel, seller, transmission, owner, listed_at, listed_at_source "
    "FROM offers WHERE offer_id = 1"
)


def test_duplicate_cards_detected(edge_conn):
    edge_conn.execute(COPY_OFFER_SQL)
    findings = checks.duplicate_findings(edge_conn)
    assert findings
    assert all(item["rule_code"] == "QA-DUPLICATE" for item in findings)


def test_range_rule_flags_old_year_and_huge_mileage(edge_conn):
    findings = checks.range_findings(edge_conn)
    messages = " ".join(item["message"] for item in findings)
    assert "1988" in messages
    assert "900000" in messages


def test_catalog_rule_flags_everything_with_empty_catalog(conn):
    assert len(checks.catalog_findings(conn)) == 6


def test_metrics_expose_expected_keys(conn):
    metrics = checks.metrics(conn)
    assert metrics["offers"] == 6
    assert 0 <= metrics["completeness_pct"] <= 100
    assert "duplicates_pct" in metrics


def test_collect_returns_all_groups(conn):
    codes = {item["rule_code"] for item in checks.collect(conn)}
    assert {"QA-FUEL-ENGINE", "QA-CATALOG-MISS"} <= codes
    assert len(THRESHOLDS) >= 4
