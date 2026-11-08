"""Тесты продакшен-обвязки: конфиг из окружения, логи, миграции, readiness."""

from __future__ import annotations

import importlib
import json
import logging
import sqlite3

import pytest
from starlette.responses import Response

import app as application
from scripts import migrate
from shared import config, logs


def test_env_text_uses_fallback(monkeypatch):
    monkeypatch.delenv("LADA_SAMPLE_VALUE", raising=False)
    assert config.env_text("LADA_SAMPLE_VALUE", "fallback") == "fallback"


def test_env_text_reads_environment(monkeypatch):
    monkeypatch.setenv("LADA_SAMPLE_VALUE", "из окружения")
    assert config.env_text("LADA_SAMPLE_VALUE", "fallback") == "из окружения"


def test_env_path_returns_path(monkeypatch, tmp_path):
    monkeypatch.setenv("LADA_SAMPLE_PATH", str(tmp_path))
    assert config.env_path("LADA_SAMPLE_PATH", config.DATA_DIR) == tmp_path


def test_environment_defaults_are_dev():
    assert config.ENVIRONMENT in {"dev", "prod"}


def test_port_and_workers_are_numbers():
    assert isinstance(config.PORT, int)
    assert isinstance(config.WORKERS, int)
    assert config.WORKERS >= 1


def test_warehouse_can_be_overridden(monkeypatch, tmp_path):
    target = tmp_path / "custom.sqlite"
    monkeypatch.setenv("LADA_WAREHOUSE", str(target))
    try:
        assert target == importlib.reload(config).WAREHOUSE
    finally:
        monkeypatch.delenv("LADA_WAREHOUSE")
        importlib.reload(config)


def test_record_payload_has_required_fields():
    record = logging.LogRecord("lada.test", logging.INFO, __file__, 1, "hello", None, None)
    payload = logs.record_payload(record)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert {"time", "logger"} <= set(payload)


def test_context_of_returns_empty_without_fields():
    record = logging.LogRecord("lada.test", logging.INFO, __file__, 1, "hello", None, None)
    assert logs.context_of(record) == {}


def test_context_of_reads_extra_fields():
    record = logging.LogRecord("lada.test", logging.INFO, __file__, 1, "hello", None, None)
    record.fields = {"path": "/catalog"}
    assert logs.context_of(record) == {"path": "/catalog"}


def test_formatter_outputs_single_json_line():
    record = logging.LogRecord("lada.test", logging.INFO, __file__, 1, "готово", None, None)
    payload = json.loads(logs.JsonFormatter().format(record))
    assert payload["message"] == "готово"
    assert "\n" not in logs.JsonFormatter().format(record)


def test_formatter_keeps_cyrillic_readable():
    record = logging.LogRecord("lada.test", logging.INFO, __file__, 1, "витрина", None, None)
    assert "витрина" in logs.JsonFormatter().format(record)


def test_configure_returns_application_logger():
    assert logs.configure("WARNING").name == logs.LOGGER_NAME


def test_logger_is_named(caplog):
    with caplog.at_level(logging.INFO, logger=logs.LOGGER_NAME):
        logs.log_event("событие", answer=42)
    assert caplog.records[-1].fields == {"answer": 42}


def test_log_request_records_timing(caplog):
    with caplog.at_level(logging.INFO, logger=logs.LOGGER_NAME):
        logs.log_request("GET", "/catalog", 200, 0.1234)
    fields = caplog.records[-1].fields
    assert fields == {"method": "GET", "path": "/catalog", "status": 200, "seconds": 0.123}


def test_version_of_strips_extension(tmp_path):
    assert migrate.version_of(tmp_path / "0003_extra.sql") == "0003_extra"


def test_migration_files_are_sorted():
    versions = [migrate.version_of(path) for path in migrate.migration_files()]
    assert versions == sorted(versions)
    assert {"0001_schema", "0002_views"} <= set(versions)


def test_run_applies_all_migrations(tmp_path):
    conn = migrate.connect(tmp_path / "warehouse.sqlite")
    try:
        assert migrate.run(conn) == ["0001_schema", "0002_views"]
    finally:
        conn.close()


def test_second_run_applies_nothing(tmp_path):
    conn = migrate.connect(tmp_path / "warehouse.sqlite")
    try:
        migrate.run(conn)
        assert migrate.run(conn) == []
    finally:
        conn.close()


def test_applied_versions_after_run(tmp_path):
    conn = migrate.connect(tmp_path / "warehouse.sqlite")
    try:
        migrate.run(conn)
        assert migrate.applied_versions(conn) == {"0001_schema", "0002_views"}
    finally:
        conn.close()


def test_schema_migrations_table_records_time(tmp_path):
    conn = migrate.connect(tmp_path / "warehouse.sqlite")
    try:
        migrate.run(conn)
        rows = conn.execute("SELECT version, applied_at FROM schema_migrations").fetchall()
    finally:
        conn.close()
    assert all(len(row["applied_at"]) >= 19 for row in rows)


def test_migrate_creates_core_tables(tmp_path):
    migrate.migrate(tmp_path / "warehouse.sqlite")
    conn = sqlite3.connect(tmp_path / "warehouse.sqlite")
    try:
        query = "SELECT name FROM sqlite_master WHERE type='table'"
        names = {row[0] for row in conn.execute(query)}
    finally:
        conn.close()
    assert {"offers", "catalog_models", "schema_migrations"} <= names


def test_apply_pending_skips_done(tmp_path):
    conn = migrate.connect(tmp_path / "warehouse.sqlite")
    files = migrate.migration_files()
    try:
        migrate.ensure_bookkeeping(conn)
        assert migrate.apply_pending(conn, files, {migrate.version_of(files[0])}) == ["0002_views"]
    finally:
        conn.close()


def test_init_db_records_migrations(empty_conn):
    assert empty_conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2


def test_readiness_report_ready():
    assert application.readiness_report(2, 8128)["status"] == "ready"


@pytest.mark.parametrize("migrations,offers", [(None, 5), (2, None), (0, 0)])
def test_readiness_report_not_ready(migrations, offers):
    assert application.readiness_report(migrations, offers)["status"] == "not-ready"


def test_ready_code_is_200_for_ready():
    assert application.ready_code({"status": "ready"}) == 200


def test_ready_code_is_503_for_not_ready():
    assert application.ready_code({"status": "not-ready"}) == 503


def test_health_is_degraded_without_schema(tmp_path):
    conn = sqlite3.connect(tmp_path / "empty.sqlite")
    try:
        assert application.counts(conn)["status"] == "degraded"
    finally:
        conn.close()


def test_ready_returns_503_without_schema(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "empty.sqlite")
    monkeypatch.setattr(application, "connect", lambda: conn)
    response = application.ready()
    assert response.status_code == 503
    assert json.loads(response.body)["status"] == "not-ready"
    conn.close()


def test_ready_returns_200_on_filled_warehouse(conn, monkeypatch):
    monkeypatch.setattr(application, "connect", lambda: conn)
    response = application.ready()
    assert response.status_code == 200
    assert json.loads(response.body)["migrations"] == 2


def test_migrated_but_empty_warehouse_is_not_ready(empty_conn, monkeypatch):
    monkeypatch.setattr(application, "connect", lambda: empty_conn)
    assert application.ready().status_code == 503


def test_recorded_returns_response_and_logs(request_factory, caplog):
    request = request_factory("/catalog")
    with caplog.at_level(logging.INFO, logger=logs.LOGGER_NAME):
        response = application.recorded(request, Response(status_code=204), 0.0)
    assert response.status_code == 204
    assert caplog.records[-1].fields["path"] == "/catalog"
