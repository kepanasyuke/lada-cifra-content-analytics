"""Тесты HTML-парсера карточек характеристик."""

from __future__ import annotations

from pathlib import Path

from projects.catalog_api import parser

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "catalog_page.html"


def test_parse_returns_all_cards():
    items = parser.parse_spec_cards(FIXTURE.read_text(encoding="utf-8"))
    assert len(items) == 3


def test_numbers_are_extracted_from_russian_labels():
    first = parser.parse_spec_cards(FIXTURE.read_text(encoding="utf-8"))[0]
    assert first["engine_cc"] == 1598
    assert first["power_bhp"] == 106
    assert first["seats"] == 5
    assert first["year_from"] == 2015


def test_missing_fields_become_empty_not_error():
    third = parser.parse_spec_cards(FIXTURE.read_text(encoding="utf-8"))[2]
    assert third["fuel"] == ""
    assert third["power_bhp"] is None
    assert parser.is_complete(third) is False


def test_split_complete_partitions_cards():
    complete, incomplete = parser.split_complete(
        parser.parse_spec_cards(FIXTURE.read_text(encoding="utf-8"))
    )
    assert len(complete) == 2
    assert len(incomplete) == 1


def test_unknown_markup_returns_empty_list():
    assert parser.parse_spec_cards("<html><body><p>нет карточек</p></body></html>") == []
