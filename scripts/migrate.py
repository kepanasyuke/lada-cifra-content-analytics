"""Миграции схемы витрины: применённые версии хранятся в schema_migrations.

Запуск: python -m scripts.migrate
Файлы миграций лежат в sql/migrations и применяются по возрастанию версии.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from shared.config import ROOT, WAREHOUSE
from shared.db import connect, execute, fetch_all
from shared.logs import configure, log_event

MIGRATIONS_DIR = ROOT / "sql" / "migrations"
BOOKKEEPING_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
)
"""
APPLIED_SQL = "SELECT version FROM schema_migrations"
RECORD_SQL = "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)"


def now() -> str:
    """Текущий момент в ISO-формате."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def migration_files() -> list[Path]:
    """SQL-файлы миграций по порядку версий."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def version_of(path: Path) -> str:
    """Версия миграции — имя файла без расширения."""
    return path.stem


def ensure_bookkeeping(conn: sqlite3.Connection) -> None:
    """Создаёт таблицу учёта миграций."""
    execute(conn, BOOKKEEPING_SQL)


def applied_versions(conn: sqlite3.Connection) -> set[str]:
    """Уже применённые версии."""
    return {row["version"] for row in fetch_all(conn, APPLIED_SQL)}


def apply_file(conn: sqlite3.Connection, path: Path) -> None:
    """Выполняет SQL миграции и фиксирует версию."""
    conn.executescript(path.read_text(encoding="utf-8"))
    execute(conn, RECORD_SQL, (version_of(path), now()))


def apply_one(conn: sqlite3.Connection, path: Path) -> str:
    """Применяет одну миграцию и отдаёт её версию."""
    apply_file(conn, path)
    return version_of(path)


def apply_pending(
    conn: sqlite3.Connection, files: list[Path], done: set[str]
) -> list[str]:
    """Применяет всё, что ещё не отмечено в учёте."""
    pending = [path for path in files if version_of(path) not in done]
    return [apply_one(conn, path) for path in pending]


def run(conn: sqlite3.Connection) -> list[str]:
    """Применяет неприменённые миграции и отдаёт их версии."""
    ensure_bookkeeping(conn)
    return apply_pending(conn, migration_files(), applied_versions(conn))


def migrate(path: Path = WAREHOUSE) -> list[str]:
    """Миграции на файловой базе."""
    conn = connect(path)
    try:
        return run(conn)
    finally:
        conn.close()


def announce(applied: list[str]) -> int:
    """Пишет в лог применённые версии."""
    log_event("migrations", applied=applied)
    return 0


def main() -> int:
    """Точка входа CLI."""
    configure()
    return announce(migrate())


if __name__ == "__main__":
    raise SystemExit(main())
