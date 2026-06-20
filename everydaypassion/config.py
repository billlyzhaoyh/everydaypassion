"""Wiring — assemble the builder and resolve on-disk locations.

Runtime state (built packages, cached images, seen log, favorites) lives under
EVERYDAYPASSION_HOME (default ~/.everydaypassion). The curated library ships in
the repo under data/curated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .builder import DayBuilder
from .library import CuratedLibrary
from .store import PackageStore

# Load a local .env (e.g. ANTHROPIC_API_KEY) once, on import.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv is optional; env vars still work
    pass


@dataclass(frozen=True)
class SiteConfig:
    """The two shapes this codebase runs as.

    ``local`` is the private morning ritual: the whole library (every museum,
    V&A, curated modern), an interactive server, links as live routes. ``public``
    is the publishable static subset: CC0 content only, no interactive state, and
    links/assets written as files under ``base_url`` for GitHub Pages.
    """

    public_only: bool
    base_url: str
    interactive: bool
    static: bool  # True when rendering to files, False when serving routes

    def home(self) -> str:
        return self.base_url if self.static else "/"

    def archive(self) -> str:
        return f"{self.base_url}archive.html" if self.static else "/archive"

    def day(self, date: str) -> str:
        return f"{self.base_url}day/{date}.html" if self.static else f"/day/{date}"

    def static_asset(self, name: str) -> str:
        return f"{self.base_url if self.static else '/'}static/{name}"

    def image(self, name: str) -> str:
        return f"{self.base_url if self.static else '/'}images/{name}"


LOCAL = SiteConfig(public_only=False, base_url="/", interactive=True, static=False)


def public_site(base_url: str = "/everydaypassion/") -> SiteConfig:
    base = base_url if base_url.endswith("/") else base_url + "/"
    return SiteConfig(public_only=True, base_url=base, interactive=False, static=True)


def home() -> Path:
    return Path(os.environ.get("EVERYDAYPASSION_HOME", Path.home() / ".everydaypassion"))


def curated_root() -> Path:
    env = os.environ.get("EVERYDAYPASSION_CURATED")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "data" / "curated"


def images_dir() -> Path:
    return home() / "images"


def make_store() -> PackageStore:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    return PackageStore(h)


def make_builder(online: bool = True, public_only: bool = False) -> DayBuilder:
    store = make_store()
    library = CuratedLibrary(curated_root())
    art_source = poem_source = wiki = reflection = None
    if online:
        # Imported lazily so the core/offline path needs no network deps.
        from .sources.artic import ArticSource
        from .sources.cleveland import ClevelandSource
        from .sources.curated import CuratedModernArt, CuratedModernPoems
        from .sources.met import MetSource
        from .sources.poetry import PoetrySource
        from .sources.pool import SourcePool
        from .sources.reflection import ReflectionWriter
        from .sources.smk import SmkSource
        from .sources.vam import VamSource
        from .sources.wikipedia import WikipediaClient

        images = images_dir()
        images.mkdir(parents=True, exist_ok=True)
        curated = curated_root()
        wiki = WikipediaClient()
        reflection = ReflectionWriter()
        taste_gate = reflection.taste_ok if os.environ.get("ANTHROPIC_API_KEY") else None

        # Each source gets an equal shot per day; the pool falls through on failure.
        art_source = SourcePool(
            [
                MetSource(images),
                ArticSource(images),
                ClevelandSource(images),
                SmkSource(images),
                VamSource(images),  # personal-use only; skips itself in a public build
                CuratedModernArt(curated, images),
            ],
            "art",
        )
        poem_source = SourcePool(
            [PoetrySource(taste_gate=taste_gate), CuratedModernPoems(curated)],
            "poem",
        )
    return DayBuilder(
        store=store, library=library, met=art_source, poetry=poem_source,
        wiki=wiki, reflection=reflection, public_only=public_only,
    )
