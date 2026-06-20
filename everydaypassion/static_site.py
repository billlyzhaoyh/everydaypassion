"""Static export — the publishable shape of the site for GitHub Pages.

Renders the public, CC0-only subset to plain files: ``index.html`` (today),
``day/<date>.html`` per morning, ``archive.html``, with images and CSS copied
alongside. The Claude reflection is generated here, at export time (the key lives
only in the build environment), and baked into the HTML — the published artifact
carries no key and makes no runtime calls.

Each build is fresh (``builder.build``, never ``ensure``) so a private frozen
package — which may hold V&A or curated-modern content — is never published.
The archive accumulates: past day files already in the output are folded in, so a
daily cron only needs to build today.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from . import config
from .builder import DayBuilder
from .config import SiteConfig
from .web import render

_STATIC = Path(__file__).parent / "web" / "static"


def recent_dates(end: str, days: int) -> list[str]:
    d = datetime.date.fromisoformat(end)
    return [(d - datetime.timedelta(days=i)).isoformat() for i in range(max(1, days))]


def export(out_dir: str | Path, site: SiteConfig, days: int = 1, online: bool = True) -> list[str]:
    builder = config.make_builder(online=online, public_only=site.public_only)
    dates = recent_dates(render.today(), days)
    return write_site(Path(out_dir), builder, config.images_dir(), site, dates)


def write_site(out_dir: Path, builder: DayBuilder, images_dir: Path,
               site: SiteConfig, dates: list[str]) -> list[str]:
    for sub in ("day", "images", "static"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_STATIC / "app.css", out_dir / "static" / "app.css")

    newest = max(dates)
    warnings: list[str] = []
    for date in dates:
        pkg = builder.build(date)  # always fresh + public_only — never a private frozen package
        if site.public_only and not (pkg.artwork.public_ok and pkg.poem.public_ok):
            warnings.append(f"{date}: skipped, non-public content slipped through")
            continue
        if not (pkg.artwork_reflection and pkg.poem_reflection):
            warnings.append(
                f"{date}: missing reflection "
                f"(artwork={bool(pkg.artwork_reflection)} poem={bool(pkg.poem_reflection)})"
            )
        html = render.render_day(
            pkg, site=site, date=date, pretty=render.pretty(date),
            image_url=_export_image(pkg.artwork.image_path, images_dir, out_dir / "images", site),
            is_favorite=False, is_today=date == render.today(),
        )
        (out_dir / "day" / f"{date}.html").write_text(html, encoding="utf-8")
        if date == newest:
            (out_dir / "index.html").write_text(html, encoding="utf-8")

    built = sorted((p.stem for p in (out_dir / "day").glob("*.html")), reverse=True)
    (out_dir / "archive.html").write_text(
        render.render_list(site=site, title="Past mornings", dates=built, pretty=render.pretty),
        encoding="utf-8",
    )
    return warnings


def _export_image(image_path: str | None, images_dir: Path, dest_dir: Path,
                  site: SiteConfig) -> str | None:
    """Copy a locally cached image into the output and return its site URL; a
    remote URL (uncached fallback) is linked as-is."""
    if not image_path:
        return None
    p = Path(image_path)
    if p.is_absolute() and images_dir in p.parents and p.exists():
        shutil.copyfile(p, dest_dir / p.name)
        return site.image(p.name)
    return image_path
