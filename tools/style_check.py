"""Проверка стиля кода проекта: короткие функции с единственным выходом.

Правила:
  STYLE001 — тело функции содержит больше операторов, чем разрешено;
  STYLE002 — у функции больше одного выхода (return / break / continue);
  STYLE003 — тело функции длиннее разрешённого числа строк.

Для прикладного кода: 2 оператора, 10 строк, 1 выход.
Для тестов лимиты мягче (6 операторов, 24 строки, 3 выхода), потому что
в тесте естественно несколько проверок подряд. raise выходом не считается:
это аварийный путь, а не альтернативный возврат.

Запуск: python tools/style_check.py [пути...]
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

APP_LIMITS = (2, 10, 1)
TEST_LIMITS = (6, 24, 3)
DECLARATIVE_LIMITS = (4, 24, 2)
LIMIT_TABLE = {"dags": DECLARATIVE_LIMITS, "tests": TEST_LIMITS}
EXIT_NODES = (ast.Return, ast.Break, ast.Continue)
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
DEFAULT_TARGETS = ("app.py", "shared", "projects", "scripts", "tools", "dags")
SKIP_PARTS = frozenset({".venv", "__pycache__", ".git", ".ruff_cache", ".pytest_cache"})


@dataclass(frozen=True)
class Violation:
    """Одно нарушение стиля."""

    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def is_docstring(node: ast.stmt | None) -> bool:
    """Проверяет, что узел — строковый литерал в начале блока."""
    value = getattr(node, "value", None)
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def own_children(node: ast.AST) -> list[ast.AST]:
    """Возвращает дочерние узлы, кроме вложенных функций."""
    return [child for child in ast.iter_child_nodes(node) if not isinstance(child, FUNCTION_NODES)]


def walk_own(node: ast.AST) -> Iterator[ast.AST]:
    """Обходит поддерево, не заходя во вложенные функции."""
    for child in own_children(node):
        yield child
        yield from walk_own(child)


def body_without_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    """Тело функции без docstring."""
    head = node.body[0] if node.body else None
    return node.body[1:] if is_docstring(head) else node.body


def body_line_span(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Количество строк, которое занимают операторы тела."""
    body = body_without_docstring(node)
    return 0 if not body else int(body[-1].end_lineno or 0) - int(body[0].lineno) + 1


def exits_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Все точки выхода в теле самой функции."""
    return [sub for sub in walk_own(node) if isinstance(sub, EXIT_NODES)]


def role_of(parts: tuple[str, ...]) -> str:
    """Роль файла по его каталогу."""
    return "dags" if "dags" in parts else "tests" if "tests" in parts else "app"


def kind_of(parts: tuple[str, ...]) -> str:
    """Тип файла: dags, tests или app."""
    return "tests" if "conftest.py" in parts else role_of(parts)


def limits_for(path: str) -> tuple[int, int, int]:
    """Лимиты: (операторов, строк, выходов)."""
    return LIMIT_TABLE.get(kind_of(Path(path).parts), APP_LIMITS)


def violation(path: str, node: ast.AST, code: str, message: str) -> Violation:
    """Собирает объект нарушения."""
    return Violation(path, int(node.lineno), code, message)


def statement_check(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    limit: int,
) -> list[Violation]:
    """Проверяет количество операторов в теле."""
    body = body_without_docstring(node)
    return [] if len(body) <= limit else [violation(path, node, "STYLE001", note(len(body), limit))]


def note(count: int, limit: int) -> str:
    """Текст нарушения по числу операторов."""
    return f"Операторов в теле: {count} > {limit}"


def exit_note(count: int, limit: int) -> str:
    """Текст нарушения по числу выходов."""
    return f"Выходов из функции: {count} > {limit}"


def span_note(span: int, limit: int) -> str:
    """Текст нарушения по длине тела."""
    return f"Строк в теле: {span} > {limit}"


def exit_check(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    limit: int,
) -> list[Violation]:
    """Проверяет единственность выхода."""
    count = len(exits_of(node))
    return [] if count <= limit else [violation(path, node, "STYLE002", exit_note(count, limit))]


def length_check(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    limit: int,
) -> list[Violation]:
    """Проверяет физическую длину тела."""
    span = body_line_span(node)
    return [] if span <= limit else [violation(path, node, "STYLE003", span_note(span, limit))]


def function_violations(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[Violation]:
    """Все проверки одной функции."""
    statements, lines, exits = limits_for(path)
    return [
        *statement_check(path, node, statements),
        *exit_check(path, node, exits),
        *length_check(path, node, lines),
    ]


def tree_violations(path: str, tree: ast.AST) -> list[Violation]:
    """Проверки всех функций файла."""
    functions = [node for node in ast.walk(tree) if isinstance(node, FUNCTION_NODES)]
    return [item for node in functions for item in function_violations(path, node)]


def file_violations(path: Path) -> list[Violation]:
    """Проверки одного файла."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tree_violations(str(path), tree)


def python_files(target: Path) -> list[Path]:
    """Список python-файлов цели."""
    return [target] if target.is_file() else sorted(target.rglob("*.py"))


def related_targets(names: list[str]) -> list[Path]:
    """Существующие цели из аргументов командной строки."""
    found = [path for name in names for path in python_files(Path(name))]
    return [path for path in found if not SKIP_PARTS & set(path.parts)]


def collect(targets: list[str]) -> list[Path]:
    """Файлы для проверки."""
    return related_targets(targets or list(DEFAULT_TARGETS))


def report(violations: list[Violation]) -> int:
    """Печатает отчёт и возвращает код выхода."""
    for item in violations:
        print(item.render())
    return 0 if not violations else 1


def main(argv: list[str]) -> int:
    """Точка входа CLI."""
    return report([item for path in collect(argv) for item in file_violations(path)])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
