"""Прогноз потребности: аддитивная модель Хольта-Уинтерса на stdlib.

Модель раскладывает ряд на уровень, тренд и сезонность с экспоненциальным
сглаживанием, даёт прогноз на горизонт, доверительный коридор по остаткам
и метрику качества MAPE на ретроспективе.

Ограничение метода: чтобы разделить тренд и сезонность, нужно минимум два
сезона истории. Если ряд короче, длина сезона ужимается автоматически,
а тренд стартует с нуля: модель деградирует до сглаживания, но не падает.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from functools import reduce
from itertools import accumulate
from typing import Any

from shared.db import fetch_all

SEASON_LENGTH = 12
ALPHA = 0.45
BETA = 0.12
GAMMA = 0.35
DEFAULT_HORIZON = 6
MAX_HORIZON = 12

SERIES_SQL = "SELECT period, offers, avg_price FROM v_monthly_demand ORDER BY period"


@dataclass(frozen=True)
class HwState:
    """Состояние модели: уровень, тренд и сезонные коэффициенты."""

    level: float
    trend: float
    season: tuple[float, ...]


def season_length(values: list[float]) -> int:
    """Длина сезона, которую выдерживает история."""
    return max(2, min(SEASON_LENGTH, len(values) // 2))


def initial_trend(values: list[float], length: int) -> float:
    """Стартовый тренд как разница средних двух первых сезонов."""
    head, rest = statistics.fmean(values[:length]), values[length : 2 * length]
    return (statistics.fmean(rest) - head) / length if rest else 0.0


def initial_season(values: list[float], length: int, level: float) -> tuple[float, ...]:
    """Стартовые сезонные добавки первого сезона."""
    return tuple(value - level for value in values[:length])


def initial_state(values: list[float], length: int = SEASON_LENGTH) -> HwState:
    """Начальное состояние модели по первым двум сезонам."""
    level = statistics.fmean(values[:length])
    return HwState(level, initial_trend(values, length), initial_season(values, length, level))


def replaced(season: tuple[float, ...], position: int, value: float) -> tuple[float, ...]:
    """Заменяет сезонный коэффициент по позиции."""
    return (*season[:position], value, *season[position + 1 :])


def seasonal(current: float, value: float, level: float) -> float:
    """Обновлённый сезонный коэффициент."""
    return (1 - GAMMA) * current + GAMMA * (value - level)


def shift_season(state: HwState, level: float, position: int, value: float) -> tuple[float, ...]:
    """Сезонные коэффициенты после шага."""
    return replaced(state.season, position, seasonal(state.season[position], value, level))


def next_state(state: HwState, level: float, position: int, value: float) -> HwState:
    """Пересчитывает тренд и сезонность."""
    trend = BETA * (level - state.level) + (1 - BETA) * state.trend
    return HwState(level, trend, shift_season(state, level, position, value))


def step(state: HwState, value: float, position: int) -> HwState:
    """Один шаг сглаживания."""
    level = ALPHA * (value - state.season[position]) + (1 - ALPHA) * (state.level + state.trend)
    return next_state(state, level, position, value)


def smooth(values: list[float], length: int = SEASON_LENGTH) -> HwState:
    """Прогон сглаживания по всей истории."""
    return reduce(
        lambda state, pair: step(state, pair[1], pair[0] % length),
        enumerate(values),
        initial_state(values, length),
    )


def states(values: list[float], length: int = SEASON_LENGTH) -> list[HwState]:
    """Состояния модели на каждом шаге истории."""
    return list(
        accumulate(
            enumerate(values),
            lambda state, pair: step(state, pair[1], pair[0] % length),
            initial=initial_state(values, length),
        )
    )


def fitted(values: list[float], length: int = SEASON_LENGTH) -> list[float]:
    """Сглаженные значения на истории."""
    history = states(values, length)[:-1]
    return [
        round(state.level + state.trend + state.season[index % length], 2)
        for index, state in enumerate(history)
    ]


def residuals(values: list[float], length: int = SEASON_LENGTH) -> list[float]:
    """Остатки модели на истории."""
    pairs = zip(values, fitted(values, length), strict=False)
    return [round(actual - model, 2) for actual, model in pairs]


def sigma(values: list[float], length: int = SEASON_LENGTH) -> float:
    """Стандартное отклонение остатков — ширина коридора."""
    deviation = statistics.pstdev(residuals(values, length)) if len(values) > 2 else 0.0
    return round(deviation, 2)


def projected(state: HwState, start: int, step: int, length: int) -> float:
    """Одна точка прогноза на шаге вперёд."""
    point = state.level + (step + 1) * state.trend + state.season[(start + step) % length]
    return round(max(0.0, point), 2)


def project(state: HwState, start: int, horizon: int, length: int = SEASON_LENGTH) -> list[float]:
    """Прогноз на горизонт вперёд."""
    return [projected(state, start, step, length) for step in range(horizon)]


def mape(actual: list[float], predicted: list[float]) -> float:
    """Средняя абсолютная процентная ошибка."""
    pairs = [(value, guess) for value, guess in zip(actual, predicted, strict=False) if value]
    return round(100.0 * statistics.fmean([abs(v - g) / v for v, g in pairs]), 2) if pairs else 0.0


def safe_horizon(values: list[float], horizon: int) -> int:
    """Горизонт бэктеста, который помещается в историю."""
    return max(1, min(horizon, len(values) // 2))


def predict_tail(values: list[float], step_back: int, length: int) -> list[float]:
    """Прогноз последних месяцев по усечённой истории."""
    train = values[:-step_back]
    return project(smooth(train, length), len(train) % length, step_back, length)


def backtest(
    values: list[float],
    horizon: int = DEFAULT_HORIZON,
    length: int = SEASON_LENGTH,
) -> dict[str, Any]:
    """Проверка метода на ретроспективе: обучаем на истории без хвоста."""
    step_back = safe_horizon(values, horizon)
    return backtest_result(values, step_back, length)


def backtest_result(values: list[float], step_back: int, length: int) -> dict[str, Any]:
    """Собирает отчёт бэктеста по размеру хвоста."""
    predicted = predict_tail(values, step_back, length)
    return report_of(values[-step_back:], predicted, step_back)


def report_of(tail: list[float], predicted: list[float], step_back: int) -> dict[str, Any]:
    """Отчёт бэктеста: MAPE, факт и прогноз."""
    return {
        "horizon": step_back,
        "mape": mape(tail, predicted),
        "actual": tail,
        "predicted": predicted,
    }


def month_label(year: int, offset: int) -> str:
    """Метка периода YYYY-MM по году и смещению месяца."""
    return f"{year + offset // 12:04d}-{offset % 12 + 1:02d}"


def next_period(period: str, shift: int) -> str:
    """Следующий период в формате YYYY-MM."""
    year, month = (int(part) for part in period.split("-"))
    return month_label(year, month - 1 + shift)


def forecast_points(last_period: str, points: list[float], band: float) -> list[dict[str, Any]]:
    """Точки прогноза с доверительным коридором."""
    return [
        {
            "x": next_period(last_period, index + 1),
            "y": value,
            "low": max(0.0, round(value - band * (index + 1) ** 0.5, 2)),
            "high": round(value + band * (index + 1) ** 0.5, 2),
        }
        for index, value in enumerate(points)
    ]


def series_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Месячный ряд из витрины."""
    return fetch_all(conn, SERIES_SQL)


def avg_price_of(rows: list[dict[str, Any]]) -> float:
    """Средняя цена последнего периода истории."""
    return float(rows[-1]["avg_price"] or 0) if rows else 0.0


def plan_of(forecast: list[dict[str, Any]], price: float) -> dict[str, Any]:
    """Потребность в позициях и бюджете на горизонт."""
    units = round(sum(point["y"] for point in forecast))
    return {
        "units": units,
        "budget_mln": round(units * price / 1000000.0, 2),
        "months": len(forecast),
        "avg_price": price,
    }


def empty_forecast() -> dict[str, Any]:
    """Пустой ответ, когда истории ещё нет."""
    return {"history": [], "forecast": [], "sigma": 0.0, "mape": 0.0, "plan": plan_of([], 0.0)}


def banded_points(
    rows: list[dict[str, Any]],
    points: list[float],
    band: float,
) -> list[dict[str, Any]]:
    """Точки прогноза с коридором."""
    return forecast_points(rows[-1]["period"], points, band)


def assemble(
    rows: list[dict[str, Any]],
    values: list[float],
    points: list[float],
    length: int,
) -> dict[str, Any]:
    """Собирает ответ: история, прогноз, коридор, план потребности."""
    band = sigma(values, length)
    return report_of_forecast(rows, banded_points(rows, points, band), band, values, length)


def report_of_forecast(
    rows: list[dict[str, Any]],
    forecast: list[dict[str, Any]],
    band: float,
    values: list[float],
    length: int,
) -> dict[str, Any]:
    """Отчёт прогноза: история, точки, коридор, MAPE и план."""
    return {
        "history": [{"x": row["period"], "y": row["offers"]} for row in rows],
        "forecast": forecast,
        "sigma": band,
        "mape": backtest(values, DEFAULT_HORIZON, length)["mape"],
        "plan": plan_of(forecast, avg_price_of(rows)),
    }


def project_points(values: list[float], length: int, horizon: int) -> list[float]:
    """Точки прогноза по истории."""
    return project(smooth(values, length), len(values) % length, horizon, length)


def build_points(values: list[float], rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    """Считает прогноз по готовому числовому ряду."""
    length = season_length(values)
    return assemble(rows, values, project_points(values, length, horizon), length)


def forecast_of(values: list[float], rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    """Прогноз с защитой от пустой истории."""
    return empty_forecast() if not values else build_points(values, rows, horizon)


def build_forecast(rows: list[dict[str, Any]], horizon: int = DEFAULT_HORIZON) -> dict[str, Any]:
    """Полный расчёт прогноза по истории."""
    return forecast_of([float(row["offers"]) for row in rows], rows, horizon)


def forecast(conn: sqlite3.Connection, horizon: int = DEFAULT_HORIZON) -> dict[str, Any]:
    """Прогноз спроса для API и DAG."""
    return build_forecast(series_rows(conn), horizon)


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Сводка прогноза для дашборда."""
    data = forecast(conn)
    return {
        "mape": data["mape"],
        "sigma": data["sigma"],
        "history_months": len(data["history"]),
        "last_month": data["history"][-1] if data["history"] else {},
        "plan": data["plan"],
        "next_months": data["forecast"][:3],
    }
