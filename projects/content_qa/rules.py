"""Правила качества контента: описание проверок и их SQL.

Каждое правило возвращает строки объявлений, которые нарушают требование.
Правила декларативны: новый контроль = новая запись в FIELD_RULES,
без правки раннера.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_COLUMNS = "offer_id, brand, model, name"


@dataclass(frozen=True)
class FieldRule:
    """Проверка обязательного поля карточки."""

    code: str
    title: str
    severity: str
    column: str
    message: str

    def sql(self) -> str:
        """SQL выборки объявлений с незаполненным полем."""
        return f"SELECT {BASE_COLUMNS} FROM offers WHERE {self.column} IS NULL"  # noqa: S608


@dataclass(frozen=True)
class Threshold:
    """Порог для алерта."""

    code: str
    title: str
    metric: str
    limit: float
    direction: str
    detail: str


FIELD_RULES: tuple[FieldRule, ...] = (
    FieldRule(
        "QA-FUEL-ENGINE",
        "Не указан объём двигателя",
        "warn",
        "engine_cc",
        "в карточке нет объёма двигателя",
    ),
    FieldRule(
        "QA-POWER", "Не указана мощность", "warn", "power_bhp", "в карточке нет мощности двигателя"
    ),
    FieldRule(
        "QA-TORQUE",
        "Не указан крутящий момент",
        "info",
        "torque",
        "в карточке нет крутящего момента",
    ),
    FieldRule("QA-SEATS", "Не указано число мест", "warn", "seats", "в карточке нет числа мест"),
    FieldRule(
        "QA-MILEAGE",
        "Не указан расход топлива",
        "info",
        "mileage_kmpl",
        "в карточке нет расхода топлива",
    ),
)

THRESHOLDS: tuple[Threshold, ...] = (
    Threshold(
        "ALERT-COMPLETENESS",
        "Полнота карточек ниже нормы",
        "completeness_pct",
        95.0,
        "below",
        "средняя полнота характеристик",
    ),
    Threshold(
        "ALERT-ENGINE",
        "Много карточек без объёма двигателя",
        "missing_engine_pct",
        2.0,
        "above",
        "доля карточек без объёма двигателя",
    ),
    Threshold(
        "ALERT-DUPLICATES",
        "Дубли в контенте",
        "duplicates_pct",
        1.0,
        "above",
        "доля дублирующихся объявлений",
    ),
    Threshold(
        "ALERT-PRICE",
        "Выбросы в ценах",
        "price_outliers_pct",
        1.5,
        "above",
        "доля цен вне коридора 1.5·IQR",
    ),
    Threshold(
        "ALERT-CATALOG",
        "Каталог не связан с контентом",
        "catalog_unmatched_pct",
        5.0,
        "above",
        "доля объявлений без позиции в каталоге",
    ),
)

SEVERITY_WEIGHT = {"bad": 1.0, "warn": 0.5, "info": 0.2}


def rules_frame() -> list[dict[str, str]]:
    """Список правил для интерфейса и документации."""
    return [
        {
            "code": rule.code,
            "title": rule.title,
            "severity": rule.severity,
            "scope": "field",
            "message": rule.message,
        }
        for rule in FIELD_RULES
    ]


def threshold_row(item: Threshold) -> dict[str, object]:
    """Строка порога для интерфейса."""
    return {
        "code": item.code,
        "title": item.title,
        "metric": item.metric,
        "limit": item.limit,
        "direction": item.direction,
        "detail": item.detail,
    }


def threshold_frame() -> list[dict[str, object]]:
    """Список порогов алертов."""
    return [threshold_row(item) for item in THRESHOLDS]
