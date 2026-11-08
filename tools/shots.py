"""Скриншоты страниц через Playwright и сбор ошибок консоли.

Запуск (сервер уже поднят):
    python -m tools.shots --base http://127.0.0.1:8000 --out docs/screens

Если Chromium лежит не в стандартном каталоге Playwright, путь задаётся
переменной окружения PLAYWRIGHT_CHROMIUM.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1440, "height": 1000}
MOBILE = {"width": 390, "height": 844}
DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_OUT = "docs/screens"
SETTLE_MS = 1200
TIMEOUT_MS = 30000
TARGETS = (
    ("catalog", "/catalog"),
    ("qa", "/qa"),
    ("trends", "/trends"),
    ("matrix", "/matrix"),
    ("forecast", "/forecast"),
)


def add_base_option(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Аргумент --base."""
    parser.add_argument("--base", default=DEFAULT_BASE, help="адрес приложения")
    return parser


def add_out_option(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Аргумент --out."""
    parser.add_argument("--out", default=DEFAULT_OUT, help="каталог для PNG")
    return parser


def prepare_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Навешивает на парсер оба аргумента."""
    add_out_option(add_base_option(parser))
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Собирает парсер аргументов."""
    return prepare_options(argparse.ArgumentParser(description="Скриншоты страниц проекта"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    return build_parser().parse_args(argv)


def launch(playwright: Any) -> Any:
    """Запускает Chromium: свой билд или стандартный из Playwright."""
    return playwright.chromium.launch(executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM") or None)


def collect_console(message: Any, errors: list[str]) -> None:
    """Запоминает ошибки консоли браузера."""
    if message.type == "error":
        errors.append("console: " + message.text)


def watch_page(page: Any, errors: list[str]) -> None:
    """Слушатели падений страницы и неудачных запросов."""
    page.on("pageerror", lambda error: errors.append("pageerror: " + str(error)))
    page.on("requestfailed", lambda request: errors.append("requestfailed: " + request.url))


def watch(page: Any, errors: list[str]) -> None:
    """Подключает слушатели консоли и страницы."""
    page.on("console", lambda message: collect_console(message, errors))
    watch_page(page, errors)


def collect_errors(page: Any, errors: list[str]) -> list[str]:
    """Подключает слушатели и отдаёт список, который они наполняют."""
    watch(page, errors)
    return errors


def listen(page: Any) -> list[str]:
    """Подключает слушатели и отдаёт список найденных ошибок."""
    return collect_errors(page, [])


def settle(page: Any, url: str) -> None:
    """Открывает страницу и ждёт отрисовку запросов."""
    page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)


def render(page: Any, url: str, viewport: dict[str, int]) -> None:
    """Готовит страницу к снимку."""
    page.set_viewport_size(viewport)
    settle(page, url)


def snap(page: Any, target: Path) -> str:
    """Сохраняет PNG целиком и возвращает имя файла."""
    page.screenshot(path=str(target), full_page=True)
    return target.name


def save(page: Any, url: str, viewport: dict[str, int], target: Path) -> str:
    """Снимает страницу целиком в файл."""
    render(page, url, viewport)
    return snap(page, target)


def shot(page: Any, base: str, out: Path, item: tuple[str, str], viewport: dict[str, int]) -> str:
    """Снимок одной страницы в одном разрешении."""
    target = out / f"{item[0]}-{viewport['width']}.png"
    return save(page, base + item[1], viewport, target)


def capture(page: Any, base: str, out: Path, item: tuple[str, str]) -> list[str]:
    """Снимки одной страницы в десктопном и мобильном разрешении."""
    return [shot(page, base, out, item, viewport) for viewport in (DESKTOP, MOBILE)]


def capture_pages(page: Any, base: str, out: Path) -> list[str]:
    """Имена файлов всех снимков."""
    return [name for item in TARGETS for name in capture(page, base, out, item)]


def build_report(base: str, errors: list[str], screens: list[str]) -> dict[str, Any]:
    """Отчёт, который кладётся рядом со скриншотами."""
    return {"base": base, "errors": errors, "screens": screens}


def capture_all(page: Any, base: str, out: Path) -> dict[str, Any]:
    """Снимки всех страниц и отчёт по ошибкам."""
    errors = listen(page)
    return build_report(base, errors, capture_pages(page, base, out))


def print_lines(items: list[str]) -> None:
    """Печатает по строке на каждую найденную ошибку."""
    for item in items:
        print("  " + item)


def print_report(report: dict[str, Any]) -> None:
    """Печатает итог съёмки."""
    print(f"скриншотов: {len(report['screens'])}, ошибок: {len(report['errors'])}")
    print_lines(report["errors"])


def write_report(target: Path, report: dict[str, Any]) -> None:
    """Кладёт отчёт рядом со скриншотами."""
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)


def prepared_dir(out: Path) -> Path:
    """Готовит каталог под скриншоты."""
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_browser(browser: Any, base: str, out: Path) -> dict[str, Any]:
    """Работа внутри одного браузера."""
    page = browser.new_page()
    try:
        return capture_all(page, base, out)
    finally:
        browser.close()


def run_browser_session(base: str, out: Path) -> dict[str, Any]:
    """Открывает Playwright и снимает все страницы."""
    with sync_playwright() as playwright:
        return run_browser(launch(playwright), base, out)


def shoot(base: str, out: Path) -> int:
    """Полный цикл съёмки."""
    write_report(out / "console.json", run_browser_session(base, out))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI."""
    args = parse_args(argv)
    return shoot(args.base.rstrip("/"), prepared_dir(Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
