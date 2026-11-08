"""Тесты рендера страниц и общего каркаса интерфейса."""

from __future__ import annotations

import pytest
from jinja2 import TemplateNotFound

from shared import theme
from shared.config import APP_TITLE, BRAND, NAV, VACANCY
from shared.theme import env, page

BASE_TEMPLATE = "shared/templates/base.html"


def render_base(project: str = "qa") -> str:
    """Рендерит общий каркас без страницы проекта."""
    return env.get_template(BASE_TEMPLATE).render(project=project, nav=NAV)


def test_page_returns_ok_response(request_factory):
    response = page(request_factory("/catalog"), BASE_TEMPLATE, "catalog")
    assert response.status_code == 200


def test_page_returns_html_content_type(request_factory):
    response = page(request_factory("/catalog"), BASE_TEMPLATE, "catalog")
    assert response.media_type == "text/html"


def test_base_contains_default_title():
    assert f"<title>{APP_TITLE}</title>" in render_base()


def test_base_contains_all_navigation_links():
    body = render_base()
    for slug in ("catalog", "qa", "trends", "matrix", "forecast"):
        assert f'href="/{slug}"' in body


def test_active_project_is_highlighted():
    body = render_base("trends")
    assert body.count("lc-nav__link--active") == 1
    assert 'href="/trends"' in body


def test_unknown_project_highlights_nothing():
    assert "lc-nav__link--active" not in render_base("unknown")


def test_base_renders_brand_and_vacancy():
    body = render_base()
    assert BRAND in body
    assert VACANCY in body


def test_base_links_static_assets():
    body = render_base()
    assert "/static/css/lada.css" in body
    assert "/static/js/app.js" in body
    assert "/static/js/charts.js" in body


def test_scripts_are_deferred():
    body = render_base()
    assert body.count('defer></script>') == 2


def test_unknown_template_raises(request_factory):
    with pytest.raises(TemplateNotFound):
        page(request_factory(), "no/such/template.html", "qa")


def test_autoescape_is_enabled_for_html():
    escaped = env.from_string("{{ value }}").render(value="<b>опасно</b>")
    assert "&lt;b&gt;" in escaped
    assert "<b>" not in escaped


def test_template_globals_are_exposed():
    assert env.globals["app_title"] == APP_TITLE
    assert env.globals["brand"] == BRAND
    assert env.globals["vacancy"] == VACANCY


def test_environment_has_trim_blocks():
    assert theme.env.trim_blocks is True
    assert theme.env.lstrip_blocks is True


@pytest.mark.parametrize(
    "template",
    [
        "projects/catalog_api/templates/index.html",
        "projects/content_qa/templates/index.html",
        "projects/trend_radar/templates/index.html",
        "projects/matrix_optimizer/templates/index.html",
        "projects/demand_forecast/templates/index.html",
    ],
)
def test_project_templates_render(template, request_factory):
    response = page(request_factory(), template, "catalog")
    assert response.status_code == 200
    assert "lc-main" in response.body.decode("utf-8")
