"""Общие фикстуры корневых тестов: витрина, пустая база и поддельные запросы."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from projects.conftest import EDGE_ROWS, SAMPLE_ROWS, prepared_db
from scripts.build_dataset import init_db


def request_for(path: str = "/catalog", port: int = 8123) -> Request:
    """Минимальный ASGI-запрос для проверок страниц и адресов."""
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "server": ("127.0.0.1", port),
            "root_path": "",
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


@pytest.fixture
def conn(tmp_path):
    """Наполненная тестовая база."""
    db = prepared_db(tmp_path / "test.sqlite", SAMPLE_ROWS)
    yield db
    db.close()


@pytest.fixture
def edge_conn(tmp_path):
    """База с граничными объявлениями."""
    db = prepared_db(tmp_path / "edge.sqlite", SAMPLE_ROWS + EDGE_ROWS)
    yield db
    db.close()


@pytest.fixture
def empty_conn(tmp_path):
    """Пустая база со схемой и вьюхами."""
    db = init_db(tmp_path / "empty.sqlite")
    yield db
    db.close()


@pytest.fixture
def request_factory():
    """Собирает запросы с любым путём и портом."""
    return request_for
