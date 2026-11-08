"""Тесты собственного чекера стиля: лимиты, выходы, отчёт."""

from __future__ import annotations

import ast

from tools import style_check

CLEAN = """
def area(width, height):
    \"\"\"Площадь прямоугольника.\"\"\"
    return width * height
"""

THREE_STATEMENTS = """
def messy(value):
    first = value + 1
    second = first * 2
    return second
"""

TWO_RETURNS = """
def pick(value):
    if value:
        return 1
    return 0
"""

RAISE_ONLY_PATH = """
def guard(value):
    if value is None:
        raise ValueError("пусто")
    return value
"""

NESTED = """
def outer():
    def inner(value):
        first = value + 1
        second = first * 2
        third = second + 3
        return third

    return inner
"""


def write(tmp_path, name, source):
    """Пишет python-файл по относительному пути внутри tmp_path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def codes_of(tmp_path, source, name="app_module.py"):
    """Коды нарушений файла с заданным исходником."""
    return [item.code for item in style_check.file_violations(write(tmp_path, name, source))]


def test_clean_function_has_no_violations(tmp_path):
    assert codes_of(tmp_path, CLEAN) == []


def test_three_statements_hit_style001(tmp_path):
    assert codes_of(tmp_path, THREE_STATEMENTS) == ["STYLE001"]


def test_two_returns_hit_style002(tmp_path):
    assert codes_of(tmp_path, TWO_RETURNS) == ["STYLE002"]


def test_long_body_hits_style003(tmp_path):
    source = "def long_one(value):\n" + "".join(
        f"    step_{index} = value + {index}\n" for index in range(11)
    )
    source += "    return step_10\n"
    assert "STYLE003" in codes_of(tmp_path, source)


def test_raise_is_not_counted_as_exit(tmp_path):
    assert codes_of(tmp_path, RAISE_ONLY_PATH) == []


def test_nested_function_reported_once(tmp_path):
    assert codes_of(tmp_path, NESTED) == ["STYLE001"]


def test_docstring_is_not_a_statement(tmp_path):
    assert codes_of(tmp_path, CLEAN) == []


def test_docstring_span_excluded_from_length():
    node = ast.parse(CLEAN).body[0]
    assert style_check.body_line_span(node) == 1


def test_limits_for_app_code(tmp_path):
    assert style_check.limits_for(str(tmp_path / "app.py")) == style_check.APP_LIMITS


def test_limits_for_tests(tmp_path):
    path = tmp_path / "tests" / "test_sample.py"
    assert style_check.limits_for(str(path)) == style_check.TEST_LIMITS


def test_limits_for_dags(tmp_path):
    path = tmp_path / "dags" / "sample_dag.py"
    assert style_check.limits_for(str(path)) == style_check.DECLARATIVE_LIMITS


def test_conftest_uses_test_limits(tmp_path):
    assert style_check.kind_of(("projects", "conftest.py")) == "tests"


def test_role_of_detects_directories():
    assert style_check.role_of(("dags", "a.py")) == "dags"
    assert style_check.role_of(("projects", "x", "tests", "a.py")) == "tests"
    assert style_check.role_of(("shared", "db.py")) == "app"


def test_violation_renders_location_and_code():
    item = style_check.Violation("app.py", 12, "STYLE001", "Операторов в теле: 3 > 2")
    assert item.render() == "app.py:12: STYLE001 Операторов в теле: 3 > 2"


def test_is_docstring_detects_string_and_code():
    tree = ast.parse('"""Док."""\nx = 1\n')
    assert style_check.is_docstring(tree.body[0]) is True
    assert style_check.is_docstring(tree.body[1]) is False


def test_body_without_docstring_drops_first_string():
    node = ast.parse(CLEAN).body[0]
    assert len(style_check.body_without_docstring(node)) == 1


def test_own_children_excludes_nested_defs():
    node = ast.parse(NESTED).body[0]
    names = [child.__class__.__name__ for child in style_check.own_children(node)]
    assert "FunctionDef" not in names


def test_exits_of_counts_return_break_continue():
    node = ast.parse("def loop(items):\n    for item in items:\n        break\n").body[0]
    assert len(style_check.exits_of(node)) == 1


def test_walk_own_skips_nested_function_bodies():
    node = ast.parse(NESTED).body[0]
    assert style_check.exits_of(node) == [node.body[-1]]


def test_statement_check_reports_count():
    node = ast.parse(THREE_STATEMENTS).body[0]
    violations = style_check.statement_check("app.py", node, 2)
    assert violations[0].code == "STYLE001"
    assert "3" in violations[0].message


def test_exit_check_is_silent_within_limit():
    node = ast.parse(TWO_RETURNS).body[0]
    assert style_check.exit_check("app.py", node, 2) == []


def test_length_check_reports_span():
    node = ast.parse(CLEAN).body[0]
    assert style_check.length_check("app.py", node, 0)[0].code == "STYLE003"


def test_function_violations_combine_all_checks():
    source = TWO_RETURNS + "\ndef extra():\n    first = 1\n    second = 2\n    return second\n"
    tree = ast.parse(source)
    found = [
        item.code for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        for item in style_check.function_violations("app.py", node)
    ]
    assert {"STYLE001", "STYLE002"} <= set(found)


def test_tree_violations_checks_every_function():
    tree = ast.parse(THREE_STATEMENTS + "\n" + TWO_RETURNS)
    codes = [item.code for item in style_check.tree_violations("app.py", tree)]
    assert codes.count("STYLE001") == 1
    assert codes.count("STYLE002") == 1


def test_python_files_lists_single_file(tmp_path):
    path = write(tmp_path, "single.py", CLEAN)
    assert style_check.python_files(path) == [path]


def test_python_files_walks_directory(tmp_path):
    write(tmp_path, "one.py", CLEAN)
    write(tmp_path, "nested/two.py", CLEAN)
    assert len(style_check.python_files(tmp_path)) == 2


def test_related_targets_skips_virtualenv(tmp_path, monkeypatch):
    write(tmp_path, ".venv/lib.py", THREE_STATEMENTS)
    write(tmp_path, "shared/db.py", CLEAN)
    monkeypatch.chdir(tmp_path)
    assert [path.name for path in style_check.related_targets(["shared"])] == ["db.py"]


def test_related_targets_ignores_missing_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert style_check.related_targets(["нет-такого"]) == []


def test_collect_returns_python_files_of_repository():
    files = style_check.collect(["shared"])
    assert files
    assert all(path.suffix == ".py" for path in files)


def test_report_returns_zero_without_violations(capsys):
    assert style_check.report([]) == 0
    assert capsys.readouterr().out == ""


def test_report_prints_each_violation(capsys):
    item = style_check.Violation("app.py", 3, "STYLE001", "сообщение")
    assert style_check.report([item]) == 1
    assert "app.py:3: STYLE001 сообщение" in capsys.readouterr().out


def test_main_reports_clean_file(tmp_path):
    path = write(tmp_path, "clean.py", CLEAN)
    assert style_check.main([str(path)]) == 0


def test_main_reports_dirty_file(tmp_path):
    path = write(tmp_path, "dirty.py", THREE_STATEMENTS)
    assert style_check.main([str(path)]) == 1
