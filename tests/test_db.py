"""Тесты тонкого слоя доступа к SQLite."""

from __future__ import annotations

import sqlite3

import pytest

from shared import db
from shared.db import (
    DictConnection,
    columns_of,
    connect,
    execute,
    executemany,
    fetch_all,
    fetch_one,
    scalar,
    table_exists,
)

INSERT_MODEL_SQL = (
    "INSERT INTO catalog_models (brand, model, trim, fuel, transmission, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)


def test_connect_returns_dict_connection(tmp_path):
    connection = connect(tmp_path / "plain.sqlite")
    assert isinstance(connection, DictConnection)
    connection.close()


def test_rows_are_dict_like(conn):
    row = fetch_one(conn, "SELECT offer_id, brand FROM offers ORDER BY offer_id")
    assert row["brand"] == "LADA"
    assert set(row) == {"offer_id", "brand"}


def test_fetch_all_returns_list_of_dicts(conn):
    rows = fetch_all(conn, "SELECT offer_id FROM offers ORDER BY offer_id")
    assert [row["offer_id"] for row in rows] == [1, 2, 3, 4, 5, 6]


def test_fetch_all_respects_params(conn):
    rows = fetch_all(conn, "SELECT offer_id FROM offers WHERE offer_id > ?", (4,))
    assert [row["offer_id"] for row in rows] == [5, 6]


def test_fetch_all_on_empty_result_is_empty_list(conn):
    assert fetch_all(conn, "SELECT 1 AS x WHERE 1 = 0") == []


def test_fetch_one_returns_none_for_no_rows(conn):
    assert fetch_one(conn, "SELECT 1 AS x WHERE 1 = 0") is None


def test_scalar_returns_first_value(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM offers") == 6


def test_scalar_returns_none_for_no_rows(conn):
    assert scalar(conn, "SELECT 1 WHERE 1 = 0") is None


def test_scalar_takes_first_column_only(conn):
    assert scalar(conn, "SELECT brand, model FROM offers LIMIT 1") == "LADA"


def test_execute_reports_changed_rows(conn):
    changed = execute(conn, "UPDATE offers SET seats = 5 WHERE seats IS NULL")
    assert changed == 1


def test_execute_commits_transaction(conn):
    execute(conn, "UPDATE offers SET seller = 'Dealer' WHERE offer_id = 1")
    assert scalar(conn, "SELECT seller FROM offers WHERE offer_id = 1") == "Dealer"


def test_executemany_inserts_all_rows(conn):
    rows = [
        ("LADA", "Aura", f"Comfort {index}", "бензин", "автомат", "2026-01-01")
        for index in range(3)
    ]
    assert executemany(conn, INSERT_MODEL_SQL, rows) == 3
    assert scalar(conn, "SELECT COUNT(*) FROM catalog_models") == 3


def test_executemany_with_empty_batch_changes_nothing(conn):
    executemany(conn, INSERT_MODEL_SQL, [])
    assert scalar(conn, "SELECT COUNT(*) FROM catalog_models") == 0


def test_table_exists_finds_offers(conn):
    assert table_exists(conn, "offers") is True


def test_table_exists_rejects_missing_table(conn):
    assert table_exists(conn, "no_such_table") is False


def test_columns_of_offers_contains_core_fields(conn):
    columns = columns_of(conn, "offers")
    assert {"offer_id", "brand", "model", "price", "listed_at"} <= set(columns)


def test_columns_of_unknown_table_is_empty(conn):
    assert columns_of(conn, "no_such_table") == []


def test_get_conn_closes_connection(monkeypatch, tmp_path):
    opened = connect(tmp_path / "dep.sqlite")
    monkeypatch.setattr(db, "connect", lambda: opened)
    generator = db.get_conn()
    assert next(generator) is opened
    with pytest.raises(StopIteration):
        next(generator)
    with pytest.raises(sqlite3.ProgrammingError):
        opened.execute("SELECT 1")


def test_get_conn_yields_working_connection(monkeypatch, conn):
    monkeypatch.setattr(db, "connect", lambda: conn)
    assert db.get_conn().__next__() is conn
