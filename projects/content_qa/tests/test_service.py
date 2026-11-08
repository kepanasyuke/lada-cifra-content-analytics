"""Тесты сервиса качества контента."""

from __future__ import annotations

from projects.content_qa import service


def test_run_qa_persists_run_and_findings(conn):
    report = service.run_qa(conn)
    assert report["run_id"] == 1
    assert report["findings"] > 0
    assert 0 <= report["score"] <= 100


def test_summary_returns_last_run_and_metrics(conn):
    service.run_qa(conn)
    summary = service.summary(conn)
    assert summary["last_run"]["run_id"] == 1
    assert summary["metrics"]["offers"] == 6
    assert summary["rules"]


def test_findings_filter_by_rule(conn):
    service.run_qa(conn)
    only_engine = service.findings(conn, code="QA-FUEL-ENGINE")
    assert only_engine
    assert {item["rule_code"] for item in only_engine} == {"QA-FUEL-ENGINE"}


def test_alerts_are_saved_for_degraded_catalog_link(conn):
    service.run_qa(conn)
    codes = {item["code"] for item in service.alerts_of(conn)}
    assert "ALERT-CATALOG" in codes


def test_by_rule_aggregates_findings(conn):
    service.run_qa(conn)
    rows = service.by_rule(conn)
    assert sum(item["findings"] for item in rows) == len(service.findings(conn, limit=10000))


def test_second_run_is_independent(conn):
    service.run_qa(conn)
    second = service.run_qa(conn)
    assert second["run_id"] == 2
    assert len(service.runs(conn)) == 2


def test_findings_without_runs_returns_empty(tmp_path):
    from scripts.build_dataset import init_db

    empty = init_db(tmp_path / "empty.sqlite")
    assert service.findings(empty) == []
    empty.close()
