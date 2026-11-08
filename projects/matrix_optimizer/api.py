"""HTTP-слой проекта «Товарная матрица»."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from projects.matrix_optimizer import matrix
from shared.db import DictConnection, get_conn
from shared.theme import page

router = APIRouter(tags=["matrix"])


@router.get("/matrix", response_class=HTMLResponse)
def matrix_page(request: Request) -> HTMLResponse:
    """Страница проекта «Товарная матрица»."""
    return page(request, "projects/matrix_optimizer/templates/index.html", "matrix")


@router.get("/api/matrix/summary")
def matrix_summary(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Сводка по матрице."""
    return matrix.summary(conn)


@router.get("/api/matrix/cells")
def matrix_cells(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Девять ячеек ABC/XYZ."""
    return matrix.cells(matrix.model_frame(conn))


@router.get("/api/matrix/models")
def matrix_models(
    code: str = "",
    limit: int = Query(50, ge=1, le=500),
    conn: DictConnection = Depends(get_conn),
) -> list[dict[str, Any]]:
    """Модели матрицы, при желании — одной ячейки."""
    frame = matrix.model_frame(conn)
    return matrix.models_of(frame, code)[:limit] if code else frame[:limit]


@router.get("/api/matrix/gaps")
def matrix_gaps(
    limit: int = Query(20, ge=1, le=100), conn: DictConnection = Depends(get_conn)
) -> list[dict[str, Any]]:
    """Позиции каталога без объявлений."""
    return matrix.gaps(conn, limit)


@router.get("/api/matrix/orphans")
def matrix_orphans(
    limit: int = Query(20, ge=1, le=100), conn: DictConnection = Depends(get_conn)
) -> list[dict[str, Any]]:
    """Объявления без позиции в каталоге."""
    return matrix.orphans(conn, limit)
