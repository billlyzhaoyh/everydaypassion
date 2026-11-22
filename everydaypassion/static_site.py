"""Static export — the publishable shape of the site for GitHub Pages.

Renders the public subset (CC0 / public domain only) to plain files:
``index.html`` (newest day), ``day/<date>.html`` per morning, ``archive.html``,
with images and CSS copied alongside. The Claude reflection is generated here, at
export time (the key lives only in the build environment), and baked into the
HTML — the published artifact carries no key and makes no runtime calls.

The site is deployed as a build artifact (``actions/deploy-pages``), so nothing
rendered — and no image — is committed. What persists between runs is the
*published data* in ``data_dir`` (committed; small JSON):

- ``packages/<date>.json`` — each published day, frozen once complete; every page
  is re-rendered from these on each export, and images re-fetched if missing.
- ``seen.json`` — every ref_id ever published, so the public site doesn't repeat
  itself (the CI runner starts with an empty home every day).

Each new day is built fresh (``builder.build``, never ``ensure``) so a private
frozen package — which may hold V&A or curated-modern content — is never
published. Day pages already in ``out_dir`` (the legacy archive copied in from
``docs/``) are kept as they are.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from . import config
from .builder import DayBuilder
from .config import SiteConfig
from .models import Artwork
from .store import PackageStore
from .web import render

_STATIC = Path(__file__).parent / "web" / "static"


def recent_dates(end: str, days: int) -> list[str]:
    d = datetime.date.fromisoformat(end)
    return [(d - datetime.timedelta(days=i)).isoformat() for i in range(max(1, days))]


def export(out_dir: str | Path, site: SiteConfig, days: int = 1, online: bool = True,
           data_dir: str | Path = "data/public", rebuild: bool = False) -> list[str]:
    builder = config.make_builder(online=online, public_only=site.public_only)
    dates = recent_dates(render.today(), days)
    return write_site(Path(out_dir), builder, config.images_dir(), site, dates,
                      data_dir=Path(data_dir), rebuild=rebuild)


def write_site(out_dir: Path, builder: DayBuilder, images_dir: Path, site: SiteConfig,
               dates: list[str], *, data_dir: Path, rebuild: bool = False) -> list[str]:
    for sub in ("day", "images", "static"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_STATIC / "app.css", out_dir / "static" / "app.css")

    published = PackageStore(data_dir)
    warnings: list[str] = []
    for date in sorted(dates):  # oldest first, so the seen log grows in order
        stored = published.read(date) if published.has(date) else None
        if not rebuild:
            if stored is not None and stored.frozen:
                continue  # published and complete — frozen
            if stored is None and (out_dir / "day" / f"{date}.html").exists():
                continue  # a legacy page from before deploy-pages — frozen as is
        # always fresh + public_only, seen = the public site's own log
        pkg = builder.build(date, seen=published.seen_ids())
        if site.public_only and not (pkg.artwork.public_ok and pkg.poem.public_ok):
            warnings.append(f"{date}: skipped, non-public content slipped through")
            continue
        if not (pkg.artwork_reflection and pkg.poem_reflection):
            warnings.append(
                f"{date}: missing reflection "
                f"(artwork={bool(pkg.artwork_reflection)} poem={bool(pkg.poem_reflection)})"
            )
        if stored is not None and not pkg.frozen and not rebuild:
            warnings.append(f"{date}: rebuild still incomplete; keeping the published version")
            continue
        published.write(pkg, overwrite=True)
        published.mark_seen(pkg.artwork.ref_id, pkg.poem.ref_id)

    for date in published.archive():
        pkg = published.read(date)
        html = render.render_day(
            pkg, site=site, date=date, pretty=render.pretty(date),
            image_url=_export_image(pkg.artwork, images_dir, out_dir / "images", site),
            is_favorite=False, is_today=date == render.today(),
        )
        (out_dir / "day" / f"{date}.html").write_text(html, encoding="utf-8")

    built = sorted((p.stem for p in (out_dir / "day").glob("*.html")), reverse=True)
    if built:
        shutil.copyfile(out_dir / "day" / f"{built[0]}.html", out_dir / "index.html")
    (out_dir / "archive.html").write_text(
        render.render_list(site=site, title="Past mornings", dates=built, pretty=render.pretty),
        encoding="utf-8",
    )
    return warnings


def _download(url: str, dest: Path) -> None:
    from .sources.http import Http

    Http().download(url, dest)


def _export_image(artwork: Artwork, images_dir: Path, dest_dir: Path, site: SiteConfig,
                  download=_download) -> str | None:
    """Copy the day's image into the output and return its site URL.

    Looks for the cached file by name in ``images_dir`` (the runner's image cache)
    and re-fetches it from ``artwork.image_url`` when missing, so past days survive
    a fresh runner. A remote URL (the build couldn't cache it) is linked as-is."""
    path = artwork.image_path
    if not path:
        return None
    if "://" in path:
        return path
    name = Path(path).name
    cached = images_dir / name
    if not cached.exists() and artwork.image_url:
        try:
            download(artwork.image_url, cached)
        except Exception:  # noqa: BLE001 — fall back to linking the source image
            return artwork.image_url
    if cached.exists():
        shutil.copyfile(cached, dest_dir / name)
        return site.image(name)
    return artwork.image_url
