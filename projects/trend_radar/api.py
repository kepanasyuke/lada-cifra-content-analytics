"""HTTP-слой проекта «Тренды»."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from projects.trend_radar import analytics
from shared.db import DictConnection, get_conn
from shared.theme import page

router = APIRouter(tags=["trends"])


@router.get("/trends", response_class=HTMLResponse)
def trends_page(request: Request) -> HTMLResponse:
    """Страница проекта «Тренды»."""
    return page(request, "projects/trend_radar/templates/index.html", "trends")


@router.get("/api/trends/summary")
def trends_summary(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Сводка по рынку."""
    return analytics.summary(conn)


@router.get("/api/trends/demand")
def trends_demand(
    months: int = Query(36, ge=3, le=36), conn: DictConnection = Depends(get_conn)
) -> dict[str, Any]:
    """Ряд спроса и индекс цен."""
    return {
        "demand": analytics.monthly_demand(conn, months),
        "index": analytics.price_index(conn, months),
    }


@router.get("/api/trends/brands")
def trends_brands(
    months: int = Query(12, ge=3, le=36), conn: DictConnection = Depends(get_conn)
) -> list[dict[str, Any]]:
    """Ряды по ведущим брендам."""
    return analytics.brand_series(conn, months)


@router.get("/api/trends/fuel")
def trends_fuel(
    months: int = Query(12, ge=3, le=36), conn: DictConnection = Depends(get_conn)
) -> list[dict[str, Any]]:
    """Структура топлива по месяцам."""
    return analytics.fuel_mix(conn, months)


@router.get("/api/trends/correlations")
def trends_correlations(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Корреляции характеристик и цены."""
    return analytics.correlation_pairs(conn)


@router.get("/api/trends/movers")
def trends_movers(conn: DictConnection = Depends(get_conn)) -> list[dict[str, Any]]:
    """Бренды с ростом и падением предложения."""
    return analytics.movers(conn)
