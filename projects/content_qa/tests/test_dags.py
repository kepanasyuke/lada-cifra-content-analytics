"""Тесты DAG-файлов: синтаксис, dag_id и связка с сервисами."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DAGS_DIR = Path(__file__).resolve().parents[3] / "dags"
DAG_FILES = sorted(DAGS_DIR.glob("*_dag.py"))
EXPECTED_DAG_IDS = {
    "catalog_ingest_dag": "catalog_ingest",
    "content_quality_dag": "content_quality",
}


def call_keywords(tree: ast.AST) -> list[ast.keyword]:
    """Все именованные аргументы вызовов файла."""
    return [
        keyword
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg
    ]


def dag_ids(path):
    """Идентификаторы DAG, объявленные в файле."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [str(keyword.value.value) for keyword in call_keywords(tree) if keyword.arg == "dag_id"]


def test_dags_present():
    assert len(DAG_FILES) == 2


@pytest.mark.parametrize("path", DAG_FILES, ids=[path.stem for path in DAG_FILES])
def test_dag_compiles(path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


@pytest.mark.parametrize("path", DAG_FILES, ids=[path.stem for path in DAG_FILES])
def test_dag_declares_expected_id(path):
    assert dag_ids(path) == [EXPECTED_DAG_IDS[path.stem]]


@pytest.mark.parametrize("path", DAG_FILES, ids=[path.stem for path in DAG_FILES])
def test_dag_declares_schedule_and_start_date(path):
    source = path.read_text(encoding="utf-8")
    assert "schedule=" in source
    assert "start_date=" in source


def test_dags_call_project_services():
    source = " ".join(path.read_text(encoding="utf-8") for path in DAG_FILES)
    assert "projects.catalog_api.service" in source
    assert "projects.content_qa.service" in source


def test_dag_imports_airflow_decorators():
    source = " ".join(path.read_text(encoding="utf-8") for path in DAG_FILES)
    assert "from airflow.decorators import dag, task" in source
