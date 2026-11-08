"""Тесты настроек проекта: пути, навигация, константы."""

from __future__ import annotations

from shared import config


def test_root_points_to_repository():
    assert (config.ROOT / "app.py").is_file()
    assert (config.ROOT / "pyproject.toml").is_file()


def test_data_paths_are_inside_root():
    assert config.DATA_DIR.parent == config.ROOT
    assert config.RAW_DIR.parent == config.DATA_DIR
    assert config.RAW_CSV.parent == config.RAW_DIR


def test_static_and_template_dirs_exist():
    assert config.STATIC_DIR.is_dir()
    assert config.TEMPLATES_DIR.is_dir()


def test_warehouse_has_sqlite_suffix():
    assert config.WAREHOUSE.name == "warehouse.sqlite"
    assert config.RAW_CSV.suffix == ".csv"


def test_brand_strings_are_filled():
    assert config.BRAND in config.APP_TITLE
    assert config.BRAND_TAGLINE
    assert config.APP_TITLE.endswith("Content Analytics")


def test_vacancy_matches_requirements():
    assert config.VACANCY == "Junior Content Analyst"


def test_nav_has_five_projects():
    assert len(config.NAV) == 5


def test_nav_keys_are_unique():
    keys = [slug for slug, _, _ in config.NAV]
    assert len(keys) == len(set(keys))


def test_nav_hrefs_are_absolute_and_match_slugs():
    for slug, _, href in config.NAV:
        assert href == f"/{slug}"
        assert href.startswith("/")


def test_nav_titles_are_not_empty():
    assert all(title.strip() for _, title, _ in config.NAV)


def test_nav_order_matches_product_flow():
    assert [slug for slug, _, _ in config.NAV] == [
        "catalog",
        "qa",
        "trends",
        "matrix",
        "forecast",
    ]


def test_short_months_cover_year():
    assert len(config.MONTHS_RU) == 12
    assert len(set(config.MONTHS_RU)) == 12


def test_short_months_are_three_letters():
    assert all(len(name) == 3 for name in config.MONTHS_RU)
