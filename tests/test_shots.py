"""Тесты снимателя скриншотов: аргументы, имена файлов, отчёт."""

from __future__ import annotations

import argparse
import json

import pytest

pytest.importorskip("playwright.sync_api")

from tools import shots


class FakePage:
    """Страница-заглушка, запоминающая вызовы вместо реального браузера."""

    def __init__(self) -> None:
        self.handlers = {}
        self.viewports = []
        self.visited = []
        self.shots = []

    def on(self, event, handler) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def set_viewport_size(self, viewport) -> None:
        self.viewports.append(viewport)

    def goto(self, url, **_kwargs) -> None:
        self.visited.append(url)

    def wait_for_timeout(self, _milliseconds) -> None:
        return None

    def screenshot(self, path, **_kwargs) -> None:
        self.shots.append(path)


class FakeBrowser:
    """Браузер-заглушка с одной страницей."""

    def __init__(self) -> None:
        self.page = FakePage()
        self.closed = False

    def new_page(self):
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeMessage:
    """Сообщение консоли браузера."""

    def __init__(self, kind: str, text: str = "") -> None:
        self.type = kind
        self.text = text


def test_default_base_and_out():
    args = shots.parse_args([])
    assert args.base == shots.DEFAULT_BASE
    assert args.out == shots.DEFAULT_OUT


def test_custom_base_and_out():
    args = shots.parse_args(["--base", "http://127.0.0.1:9000", "--out", "tmp/shots"])
    assert args.base == "http://127.0.0.1:9000"
    assert args.out == "tmp/shots"


def test_parser_has_description():
    assert shots.build_parser().description == "Скриншоты страниц проекта"


def test_base_option_returns_parser():
    parser = shots.add_base_option(argparse.ArgumentParser())
    assert parser.parse_args([]).base == shots.DEFAULT_BASE


def test_out_option_returns_parser():
    parser = shots.add_out_option(argparse.ArgumentParser())
    assert parser.parse_args([]).out == shots.DEFAULT_OUT


def test_targets_cover_five_pages():
    assert [name for name, _ in shots.TARGETS] == [
        "catalog",
        "qa",
        "trends",
        "matrix",
        "forecast",
    ]


def test_build_report_shape():
    report = shots.build_report("http://x", [], ["a.png"])
    assert report == {"base": "http://x", "errors": [], "screens": ["a.png"]}


def test_prepared_dir_creates_nested_folder(tmp_path):
    target = shots.prepared_dir(tmp_path / "docs" / "screens")
    assert target.is_dir()
    assert target == tmp_path / "docs" / "screens"


def test_prepared_dir_is_idempotent(tmp_path):
    shots.prepared_dir(tmp_path)
    assert shots.prepared_dir(tmp_path) == tmp_path


def test_print_lines_writes_each_error(capsys):
    shots.print_lines(["первая", "вторая"])
    assert capsys.readouterr().out.splitlines() == ["  первая", "  вторая"]


def test_print_report_summarises_counts(capsys):
    shots.print_report({"screens": ["a", "b"], "errors": []})
    assert "скриншотов: 2, ошибок: 0" in capsys.readouterr().out


def test_write_report_saves_json(tmp_path, capsys):
    target = tmp_path / "console.json"
    shots.write_report(target, {"screens": ["a.png"], "errors": []})
    assert json.loads(target.read_text(encoding="utf-8"))["screens"] == ["a.png"]
    assert "скриншотов: 1" in capsys.readouterr().out


def test_collect_console_keeps_only_errors():
    errors = []
    shots.collect_console(FakeMessage("warning", "шум"), errors)
    shots.collect_console(FakeMessage("error", "падение"), errors)
    assert errors == ["console: падение"]


def test_watch_page_registers_failure_handlers():
    page = FakePage()
    shots.watch_page(page, [])
    assert set(page.handlers) == {"pageerror", "requestfailed"}


def test_watch_registers_console_handler():
    page = FakePage()
    shots.watch(page, [])
    assert set(page.handlers) == {"console", "pageerror", "requestfailed"}


def test_listen_collects_errors_from_handlers():
    page = FakePage()
    errors = shots.listen(page)
    page.handlers["pageerror"][0](RuntimeError("boom"))
    assert errors == ["pageerror: boom"]


def test_settle_waits_for_network_idle():
    page = FakePage()
    shots.settle(page, "http://127.0.0.1:8000/catalog")
    assert page.visited == ["http://127.0.0.1:8000/catalog"]


def test_render_sets_viewport_before_navigation():
    page = FakePage()
    shots.render(page, "http://x/qa", shots.MOBILE)
    assert page.viewports == [shots.MOBILE]


def test_snap_returns_file_name(tmp_path):
    page = FakePage()
    assert shots.snap(page, tmp_path / "catalog-390.png") == "catalog-390.png"


def test_save_writes_full_page(tmp_path):
    page = FakePage()
    shots.save(page, "http://x/catalog", shots.DESKTOP, tmp_path / "catalog-1440.png")
    assert page.shots == [str(tmp_path / "catalog-1440.png")]


def test_shot_builds_name_from_page_and_width(tmp_path):
    page = FakePage()
    name = shots.shot(page, "http://x", tmp_path, ("qa", "/qa"), shots.MOBILE)
    assert name == "qa-390.png"


def test_capture_takes_two_resolutions(tmp_path):
    page = FakePage()
    names = shots.capture(page, "http://x", tmp_path, ("matrix", "/matrix"))
    assert names == ["matrix-1440.png", "matrix-390.png"]


def test_capture_pages_covers_all_targets(tmp_path):
    page = FakePage()
    names = shots.capture_pages(page, "http://x", tmp_path)
    assert len(names) == 10


def test_capture_all_has_no_errors(tmp_path):
    report = shots.capture_all(FakePage(), "http://x", tmp_path)
    assert report["errors"] == []
    assert len(report["screens"]) == 10


def test_run_browser_closes_browser(tmp_path):
    browser = FakeBrowser()
    shots.run_browser(browser, "http://x", tmp_path)
    assert browser.closed is True


def test_launch_uses_environment_path(monkeypatch):
    class FakeChromium:
        def launch(self, **kwargs):
            return kwargs

    class FakePlaywright:
        chromium = FakeChromium()

    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM", "C:/chrome.exe")
    assert shots.launch(FakePlaywright())["executable_path"] == "C:/chrome.exe"


def test_launch_without_environment_path(monkeypatch):
    class FakeChromium:
        def launch(self, **kwargs):
            return kwargs

    class FakePlaywright:
        chromium = FakeChromium()

    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM", raising=False)
    assert shots.launch(FakePlaywright())["executable_path"] is None


def test_shoot_writes_report(tmp_path, monkeypatch, capsys):
    report = shots.build_report("u", [], ["a.png"])
    monkeypatch.setattr(shots, "run_browser_session", lambda _base, _out: report)
    assert shots.shoot("http://x", tmp_path) == 0
    assert (tmp_path / "console.json").is_file()
    assert "скриншотов: 1" in capsys.readouterr().out


def test_main_strips_trailing_slash(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(shots, "shoot", lambda base, out: seen.update(base=base, out=out) or 0)
    assert shots.main(["--base", "http://127.0.0.1:8125/", "--out", str(tmp_path)]) == 0
    assert seen["base"] == "http://127.0.0.1:8125"
