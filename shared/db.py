"""Тонкий слой доступа к SQLite: соединение и короткие хелперы запросов."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from shared.config import WAREHOUSE

Row = dict[str, Any]
Params = Sequence[Any]


class DictConnection(sqlite3.Connection):
    """Соединение, отдающее строки как словари."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.row_factory = sqlite3.Row


def connect(path: Path = WAREHOUSE) -> DictConnection:
    """Открывает соединение с базой."""
    return DictConnection(path, check_same_thread=False)


def get_conn() -> Iterator[DictConnection]:
    """FastAPI-зависимость: соединение на один запрос."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(conn: sqlite3.Connection, sql: str, params: Params = ()) -> list[Row]:
    """Возвращает все строки запроса как словари."""
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_one(conn: sqlite3.Connection, sql: str, params: Params = ()) -> Row | None:
    """Возвращает первую строку запроса или None."""
    row = conn.execute(sql, params).fetchone()
    return None if row is None else dict(row)


def scalar(conn: sqlite3.Connection, sql: str, params: Params = ()) -> Any:
    """Возвращает первое значение первой строки."""
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def committed(conn: sqlite3.Connection, cursor: sqlite3.Cursor) -> int:
    """Фиксирует транзакцию и отдаёт число изменённых строк."""
    conn.commit()
    return cursor.rowcount


def execute(conn: sqlite3.Connection, sql: str, params: Params = ()) -> int:
    """Выполняет запрос и фиксирует транзакцию."""
    return committed(conn, conn.execute(sql, params))


def executemany(conn: sqlite3.Connection, sql: str, rows: Iterable[Params]) -> int:
    """Выполняет пакетный запрос и фиксирует транзакцию."""
    return committed(conn, conn.executemany(sql, rows))


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Проверяет наличие таблицы."""
    return scalar(conn, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)) == 1


def columns_of(conn: sqlite3.Connection, name: str) -> list[str]:
    """Список колонок таблицы."""
    return [row["name"] for row in fetch_all(conn, f"PRAGMA table_info({name})")]
