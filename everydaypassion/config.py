"""Wiring — assemble the builder and resolve on-disk locations.

Runtime state (built packages, cached images, seen log, favorites) lives under
EVERYDAYPASSION_HOME (default ~/.everydaypassion). The curated library ships in
the repo under data/curated.
"""

from __future__ import annotations

import os
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
