"""HTTP-слой проекта «Прогноз спроса»."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from projects.demand_forecast import forecast
from shared.db import DictConnection, get_conn
from shared.theme import page

router = APIRouter(tags=["forecast"])


@router.get("/forecast", response_class=HTMLResponse)
def forecast_page(request: Request) -> HTMLResponse:
    """Страница проекта «Прогноз спроса»."""
    return page(request, "projects/demand_forecast/templates/index.html", "forecast")


@router.get("/api/forecast/summary")
def forecast_summary(conn: DictConnection = Depends(get_conn)) -> dict[str, Any]:
    """Сводка: MAPE, коридор, план потребности."""
    return forecast.summary(conn)


@router.get("/api/forecast/series")
def forecast_series(
    horizon: int = Query(forecast.DEFAULT_HORIZON, ge=1, le=forecast.MAX_HORIZON),
    conn: DictConnection = Depends(get_conn),
) -> dict[str, Any]:
    """История и прогноз с коридором."""
    return forecast.forecast(conn, horizon)


@router.get("/api/forecast/backtest")
def forecast_backtest(
    horizon: int = Query(forecast.DEFAULT_HORIZON, ge=1, le=forecast.MAX_HORIZON),
    conn: DictConnection = Depends(get_conn),
) -> dict[str, Any]:
    """Ретроспективная проверка модели."""
    values = [float(row["offers"]) for row in forecast.series_rows(conn)]
    return forecast.backtest(values, horizon)
