"""HTML rendering, decoupled from the server.

A plain Jinja environment turns a package into an HTML string. Both the live
server (which wraps it in a response) and the static exporter (which writes it
to a file) render through here, so the templates — and the local/public
differences in links, assets, and interactivity — live in exactly one place.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import SiteConfig

_TEMPLATES = Path(__file__).parent / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def today() -> str:
    return datetime.date.today().isoformat()


def pretty(date: str) -> str:
    return datetime.date.fromisoformat(date).strftime("%A · %-d %B %Y")


def image_url(site: SiteConfig, image_path: str | None, images_dir: Path) -> str | None:
    """A local cached image resolves to the site's images route; a bare remote
    URL (offline/uncached fallback) is used as-is."""
    if not image_path:
        return None
    p = Path(image_path)
    if p.is_absolute() and images_dir in p.parents:
        return site.image(p.name)
    return image_path


def render_day(pkg, *, site: SiteConfig, date: str, pretty: str,
               image_url: str | None, is_favorite: bool = False,
               is_today: bool = False) -> str:
    return _ENV.get_template("day.html").render(
        pkg=pkg, site=site, date=date, pretty=pretty, image_url=image_url,
        is_favorite=is_favorite, is_today=is_today,
    )


def render_list(*, site: SiteConfig, title: str, dates, pretty,
                is_favorite=lambda d: False) -> str:
    return _ENV.get_template("list.html").render(
        site=site, title=title, dates=dates, pretty=pretty, is_favorite=is_favorite,
    )
