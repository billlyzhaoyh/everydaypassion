"""DayBuilder — the orchestrator.

Generate-if-missing: on first access of a date it picks, fetches, reflects,
assembles, and freezes the package. Sources are injected, so the central
policy here — retry a live source briefly, then fall back to the curated
library — is fully testable with fakes and no network.
"""

from __future__ import annotations

from typing import Protocol

from .library import CuratedLibrary
from .models import Artwork, DayPackage, Poem, Reflection
from .store import PackageStore


class ArtworkSource(Protocol):
    def fetch_artwork(self, date: str, seen: set[str], public_only: bool) -> Artwork: ...


class PoemSource(Protocol):
    def fetch_poem(self, date: str, seen: set[str], public_only: bool) -> Poem: ...


class Facts(Protocol):
    def facts_for(self, artwork: Artwork) -> dict: ...


class ReflectionSource(Protocol):
    def write(self, artwork: Artwork, facts: dict) -> str: ...


class DayBuilder:
    def __init__(
        self,
        store: PackageStore,
        library: CuratedLibrary,
        met: ArtworkSource | None = None,
        poetry: PoemSource | None = None,
        wiki: Facts | None = None,
        reflection: ReflectionSource | None = None,
        retries: int = 2,
        public_only: bool = False,
    ):
        self.store = store
        self.library = library
        self.met = met
        self.poetry = poetry
        self.wiki = wiki
        self.reflection = reflection
        self.retries = max(1, retries)
        self.public_only = public_only

    def ensure(self, date: str) -> DayPackage:
        """Return the package for ``date``, building it once if missing.
        A built date is frozen and never rebuilt."""
        if self.store.has(date):
            return self.store.read(date)
        pkg = self.build(date)
        self.store.write(pkg)
        self.store.mark_seen(pkg.artwork.ref_id, pkg.poem.ref_id)
        return pkg

    def build(self, date: str) -> DayPackage:
        seen = self.store.seen_ids()
        artwork = self._fetch(
            date, seen, "artwork",
            self.met.fetch_artwork if self.met else None,
            self.library.get_artwork,
        )
        poem = self._fetch(
            date, seen, "poem",
            self.poetry.fetch_poem if self.poetry else None,
            self.library.get_poem,
        )
        reflection = self._reflection(artwork)
        return DayPackage(date=date, artwork=artwork, poem=poem, reflection=reflection, frozen=True)

    # ---- content with retry → fallback ----------------------------------
    def _fetch(self, date: str, seen: set[str], kind: str, live, fallback):
        """Fetch from the live source (with retries), falling back to the
        curated library if it's absent or fails."""
        if live is not None:
            try:
                return self._retry(
                    lambda: live(date=date, seen=seen, public_only=self.public_only)
                )
            except Exception:
                pass
        return fallback(f"{date}:{kind}", public_only=self.public_only)

    def _reflection(self, artwork: Artwork) -> Reflection | None:
        if self.wiki is None or self.reflection is None:
            return None
        try:
            facts = self._retry(lambda: self.wiki.facts_for(artwork))
            text = self._retry(lambda: self.reflection.write(artwork, facts))
            grounded = ["The Met", "Wikipedia"] if facts.get("summary") else ["The Met"]
            return Reflection(text=text, grounded_in=grounded)
        except Exception:
            return None

    def _retry(self, fn):
        last: Exception | None = None
        for _ in range(self.retries):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — policy is deliberately broad
                last = exc
        raise last  # type: ignore[misc]
