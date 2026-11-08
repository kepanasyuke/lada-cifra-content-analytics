"""HTTP-слой проекта «Качество контента»."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from projects.content_qa import service
from shared.db import DictConnection, get_conn
from shared.theme import page

router = APIRouter(tags=["content-qa"])


@router.get("/qa", response_class=HTMLResponse)
def qa_page(request: Request) -> HTMLResponse:
    """Страница проекта «Качество контента»."""
    return page(request, "projects/content_qa/templates/index.html", "qa")


@router.get("/api/qa/summary")
def qa_summary(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Сводка и текущие метрики."""
    return service.summary(conn)


@router.post("/api/qa/run")
def qa_run(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Запускает проверки качества контента."""
    return service.run_qa(conn)


@router.get("/api/qa/findings")
def qa_findings(
    code: str = "",
    limit: int = Query(200, ge=1, le=1000),
    conn: DictConnection = Depends(get_conn),
) -> list[dict[str, Any]]:
    """Нарушения последнего прогона."""
    return service.findings(conn, code=code, limit=limit)


@router.get("/api/qa/alerts")
def qa_alerts(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Алерты последнего прогона."""
    return service.alerts_of(conn)


@router.get("/api/qa/by-rule")
def qa_by_rule(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Агрегация нарушений по правилам."""
    return service.by_rule(conn)


@router.get("/api/qa/runs")
def qa_runs(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """История прогонов."""
    return service.runs(conn)
