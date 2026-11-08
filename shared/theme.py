"""Рендеринг HTML-страниц в фирменном стиле LADA Цифра."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from shared.config import APP_TITLE, BRAND, BRAND_TAGLINE, NAV, ROOT, VACANCY

env = Environment(
    loader=FileSystemLoader(ROOT),
    autoescape=select_autoescape(("html",)),
    trim_blocks=True,
    lstrip_blocks=True,
)
env.globals.update(app_title=APP_TITLE, brand=BRAND, tagline=BRAND_TAGLINE, vacancy=VACANCY)


def page(request: Request, template: str, project: str, **context: Any) -> HTMLResponse:
    """Рендерит страницу проекта внутри общего каркаса."""
    return HTMLResponse(
        env.get_template(template).render(request=request, nav=NAV, project=project, **context)
    )
