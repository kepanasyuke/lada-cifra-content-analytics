"""Алерты: превращают метрики качества в сигналы для команды контента."""

from __future__ import annotations

from typing import Any

from projects.content_qa.rules import SEVERITY_WEIGHT, THRESHOLDS, Threshold

COMPLETENESS_WEIGHT = 0.6
FINDINGS_WEIGHT = 0.4


def violated(threshold: Threshold, value: float) -> bool:
    """Проверяет выход метрики за порог."""
    return value > threshold.limit if threshold.direction == "above" else value < threshold.limit


def level_of(threshold: Threshold, value: float) -> str:
    """Уровень критичности алерта по величине отклонения."""
    return "bad" if abs(value - threshold.limit) > threshold.limit * 0.5 else "warn"


def detail_of(threshold: Threshold, value: float) -> str:
    """Текст алерта: значение против порога."""
    return f"{threshold.detail}: {value:g} (порог {threshold.direction} {threshold.limit:g})"


def alert_of(threshold: Threshold, value: float) -> dict[str, Any]:
    """Собирает объект алерта."""
    return {
        "level": level_of(threshold, value),
        "code": threshold.code,
        "title": threshold.title,
        "detail": detail_of(threshold, value),
        "metric": float(value),
        "threshold": float(threshold.limit),
    }


def build_alerts(metrics: dict[str, float]) -> list[dict[str, Any]]:
    """Все нарушенные пороги."""
    return [
        alert_of(item, metrics.get(item.metric, 0.0))
        for item in THRESHOLDS
        if violated(item, metrics.get(item.metric, 0.0))
    ]


def penalty_share(metrics: dict[str, float], findings: list[dict[str, Any]]) -> float:
    """Доля штрафа за нарушения в процентах от числа объявлений."""
    penalized = sum(SEVERITY_WEIGHT.get(item["severity"], 0.2) for item in findings)
    return 100.0 * penalized / max(1, int(metrics.get("offers", 0)))


def blend(metrics: dict[str, float], share: float) -> float:
    """Взвешенная смесь полноты и штрафа за нарушения."""
    completeness = COMPLETENESS_WEIGHT * metrics.get("completeness_pct", 0.0)
    return completeness + FINDINGS_WEIGHT * max(0.0, 100.0 - share)


def quality_score(metrics: dict[str, float], findings: list[dict[str, Any]]) -> float:
    """Итоговая оценка качества контента от 0 до 100."""
    share = penalty_share(metrics, findings)
    return round(max(0.0, blend(metrics, share)), 2)
