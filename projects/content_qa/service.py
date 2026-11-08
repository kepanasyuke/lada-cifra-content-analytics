"""Сервис проекта «Качество контента»: прогон проверок, сохранение результатов."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from projects.content_qa import alerts, checks
from projects.content_qa.rules import rules_frame, threshold_frame
from shared.db import Row, execute, executemany, fetch_all, fetch_one, scalar

FINDING_SQL = """
INSERT INTO qa_findings (run_id, rule_code, severity, scope, offer_id, brand, model, message)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

ALERT_SQL = """
INSERT INTO qa_alerts (run_id, level, code, title, detail, metric, threshold)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

BY_RULE_SQL = (
    "SELECT rule_code, severity, COUNT(*) AS findings FROM qa_findings "
    "WHERE run_id = ? GROUP BY rule_code, severity ORDER BY findings DESC"
)


def now() -> str:
    """Текущий момент в ISO-формате."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def start_run(conn: sqlite3.Connection, offers: int) -> int:
    """Создаёт запись о прогоне проверок."""
    execute(
        conn,
        "INSERT INTO qa_runs (created_at, offers, findings, alerts, score) VALUES (?, ?, 0, 0, 0)",
        (now(), offers),
    )
    return int(scalar(conn, "SELECT last_insert_rowid()") or 0)


def finding_row(run_id: int, item: dict[str, Any]) -> tuple[Any, ...]:
    """Строка вставки нарушения."""
    return (
        run_id,
        item["rule_code"],
        item["severity"],
        item["scope"],
        item["offer_id"],
        item["brand"],
        item["model"],
        item["message"],
    )


def save_findings(conn: sqlite3.Connection, run_id: int, findings: list[dict[str, Any]]) -> int:
    """Сохраняет найденные нарушения."""
    return executemany(conn, FINDING_SQL, [finding_row(run_id, item) for item in findings])


def alert_row(run_id: int, item: dict[str, Any]) -> tuple[Any, ...]:
    """Строка вставки алерта."""
    return (
        run_id,
        item["level"],
        item["code"],
        item["title"],
        item["detail"],
        item["metric"],
        item["threshold"],
    )


def save_alerts(conn: sqlite3.Connection, run_id: int, items: list[dict[str, Any]]) -> int:
    """Сохраняет алерты прогона."""
    return executemany(conn, ALERT_SQL, [alert_row(run_id, item) for item in items])


def close_run(
    conn: sqlite3.Connection,
    run_id: int,
    findings: list[dict[str, Any]],
    score: float,
    alert_count: int,
) -> dict[str, Any]:
    """Фиксирует итоги прогона."""
    execute(
        conn,
        "UPDATE qa_runs SET findings=?, alerts=?, score=? WHERE run_id=?",
        (len(findings), alert_count, score, run_id),
    )
    return {"run_id": run_id, "findings": len(findings), "alerts": alert_count, "score": score}


def finalize(
    conn: sqlite3.Connection,
    run_id: int,
    findings: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Сохраняет алерты и закрывает прогон."""
    save_alerts(conn, run_id, items)
    return close_run(
        conn, run_id, findings, alerts.quality_score(metrics_of(conn), findings), len(items)
    )


def metrics_of(conn: sqlite3.Connection) -> dict[str, float]:
    """Метрики для оценки качества."""
    return checks.metrics(conn)


def persist(
    conn: sqlite3.Connection, run_id: int, findings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Записывает нарушения, считает алерты и итог."""
    save_findings(conn, run_id, findings)
    return finalize(conn, run_id, findings, alerts.build_alerts(metrics_of(conn)))


def run_qa(conn: sqlite3.Connection) -> dict[str, Any]:
    """Полный прогон проверок качества контента."""
    run_id = start_run(conn, int(checks.metrics(conn).get("offers", 0)))
    return persist(conn, run_id, checks.collect(conn))


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Сводка по последнему прогону и текущим метрикам."""
    return {
        "last_run": last_run(conn),
        "metrics": checks.metrics(conn),
        "rules": rules_frame(),
        "thresholds": threshold_frame(),
        "latest": latest_run_id(conn),
    }


def last_run(conn: sqlite3.Connection) -> Row:
    """Последний прогон проверок."""
    return fetch_one(conn, "SELECT * FROM qa_runs ORDER BY run_id DESC LIMIT 1") or {}


def latest_run_id(conn: sqlite3.Connection) -> int:
    """Идентификатор последнего прогона."""
    return int((last_run(conn) or {}).get("run_id") or 0)


def findings_query(run_id: int, code: str) -> tuple[str, list[Any]]:
    """SQL и параметры выборки нарушений."""
    base = "SELECT * FROM qa_findings WHERE run_id = ?"
    return (f"{base} AND rule_code = ?", [run_id, code]) if code else (base, [run_id])


def findings(
    conn: sqlite3.Connection,
    run_id: int | None = None,
    code: str = "",
    limit: int = 200,
) -> list[Row]:
    """Нарушения последнего прогона с фильтрами."""
    sql, params = findings_query(run_id or latest_run_id(conn), code)
    return fetch_all(conn, sql + " ORDER BY finding_id LIMIT ?", (*params, limit))


def alerts_of(conn: sqlite3.Connection, run_id: int | None = None) -> list[Row]:
    """Алерты последнего прогона."""
    return fetch_all(
        conn,
        "SELECT * FROM qa_alerts WHERE run_id = ? ORDER BY alert_id",
        (run_id or latest_run_id(conn),),
    )


def by_rule(conn: sqlite3.Connection, run_id: int | None = None) -> list[Row]:
    """Сколько нарушений дало каждое правило."""
    return fetch_all(conn, BY_RULE_SQL, (run_id or latest_run_id(conn),))


def runs(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    """История прогонов проверок."""
    return fetch_all(conn, "SELECT * FROM qa_runs ORDER BY run_id DESC LIMIT ?", (limit,))
