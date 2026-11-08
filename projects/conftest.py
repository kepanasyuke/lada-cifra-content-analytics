"""Общие фикстуры тестов: тестовая витрина с небольшим набором объявлений."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.build_dataset import INSERT_SQL, init_db, normalize, offer_tuple
from shared.db import executemany

SAMPLE_ROWS: list[dict[str, str]] = [
    {
        "name": "LADA Vesta Comfort",
        "year": "2018",
        "selling_price": "620000",
        "km_driven": "45000",
        "fuel": "бензин",
        "seller_type": "Dealer",
        "transmission": "механика",
        "owner": "First Owner",
        "mileage": "17.5 kmpl",
        "engine": "1598 CC",
        "max_power": "106 bhp",
        "torque": "148Nm",
        "seats": "5",
    },
    {
        "name": "LADA Vesta Comfort",
        "year": "2019",
        "selling_price": "690000",
        "km_driven": "32000",
        "fuel": "бензин",
        "seller_type": "Dealer",
        "transmission": "механика",
        "owner": "First Owner",
        "mileage": "16.9 kmpl",
        "engine": "1598 CC",
        "max_power": "106 bhp",
        "torque": "148Nm",
        "seats": "5",
    },
    {
        "name": "LADA Niva Legend Urban",
        "year": "2021",
        "selling_price": "780000",
        "km_driven": "18000",
        "fuel": "бензин",
        "seller_type": "Individual",
        "transmission": "механика",
        "owner": "First Owner",
        "mileage": "",
        "engine": "1690 CC",
        "max_power": "83 bhp",
        "torque": "",
        "seats": "5",
    },
    {
        "name": "LADA Granta Standard",
        "year": "2016",
        "selling_price": "410000",
        "km_driven": "120000",
        "fuel": "бензин",
        "seller_type": "Individual",
        "transmission": "механика",
        "owner": "Second Owner",
        "mileage": "18.5 kmpl",
        "engine": "",
        "max_power": "",
        "torque": "",
        "seats": "",
    },
    {
        "name": "LADA Vesta SW Cross",
        "year": "2020",
        "selling_price": "910000",
        "km_driven": "27000",
        "fuel": "бензин",
        "seller_type": "Trustmark Dealer",
        "transmission": "вариатор",
        "owner": "First Owner",
        "mileage": "15.8 kmpl",
        "engine": "1774 CC",
        "max_power": "122 bhp",
        "torque": "170Nm",
        "seats": "5",
    },
    {
        "name": "LADA XRAY Cross",
        "year": "2019",
        "selling_price": "760000",
        "km_driven": "54000",
        "fuel": "бензин",
        "seller_type": "Dealer",
        "transmission": "механика",
        "owner": "First Owner",
        "mileage": "16.4 kmpl",
        "engine": "1774 CC",
        "max_power": "122 bhp",
        "torque": "170Nm",
        "seats": "5",
    },
]

EDGE_ROWS: list[dict[str, str]] = [
    {
        "name": "LADA Kalina Standard",
        "year": "2012",
        "selling_price": "3000",
        "km_driven": "210000",
        "fuel": "бензин",
        "seller_type": "Individual",
        "transmission": "механика",
        "owner": "Third Owner",
        "mileage": "16.0 kmpl",
        "engine": "1596 CC",
        "max_power": "82 bhp",
        "torque": "132Nm",
        "seats": "5",
    },
    {
        "name": "LADA 2107 Classic",
        "year": "1988",
        "selling_price": "120000",
        "km_driven": "900000",
        "fuel": "бензин",
        "seller_type": "Individual",
        "transmission": "механика",
        "owner": "Fourth & Above Owner",
        "mileage": "12.0 kmpl",
        "engine": "1569 CC",
        "max_power": "74 bhp",
        "torque": "116Nm",
        "seats": "5",
    },
]


def rows_to_tuples(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """Нормализует строки CSV-подобного вида в кортежи."""
    return [offer_tuple(normalize(row, index)) for index, row in enumerate(rows, start=1)]


def seed(db, rows: list[dict[str, str]]) -> Any:
    """Наполняет тестовую базу объявлениями."""
    executemany(db, INSERT_SQL, rows_to_tuples(rows))
    return db


def prepared_db(path: Path, rows: list[dict[str, str]]) -> Any:
    """Готовая тестовая база со схемой и данными."""
    return seed(init_db(path), rows)


@pytest.fixture
def conn(tmp_path):
    """Соединение с наполненной тестовой базой."""
    db = prepared_db(tmp_path / "test.sqlite", SAMPLE_ROWS)
    yield db
    db.close()


@pytest.fixture
def edge_conn(tmp_path):
    """База с граничными случаями: дешёвая карточка, древний год, огромный пробег."""
    db = prepared_db(tmp_path / "edge.sqlite", SAMPLE_ROWS + EDGE_ROWS)
    yield db
    db.close()
