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

# A curator note this long or longer stands on its own — show it verbatim and skip
# the LLM. Shorter than this, the writer composes from facts instead.
MIN_CURATOR_NOTE = 120


class ArtworkSource(Protocol):
    def fetch_artwork(self, date: str, seen: set[str], public_only: bool) -> Artwork: ...


class PoemSource(Protocol):
    def fetch_poem(self, date: str, seen: set[str], public_only: bool) -> Poem: ...


class Facts(Protocol):
    def facts_for(self, artwork: Artwork) -> dict: ...
    def facts_for_poet(self, poem: Poem) -> dict: ...


class ReflectionSource(Protocol):
    def write(self, artwork: Artwork, facts: dict) -> str: ...
    def write_poem(self, poem: Poem, facts: dict) -> str: ...


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
        return DayPackage(
            date=date,
            artwork=artwork,
            poem=poem,
            artwork_reflection=self._artwork_reflection(artwork),
            poem_reflection=self._reflect(
                poem.source,
                lambda: self.wiki.facts_for_poet(poem),
                lambda facts: self.reflection.write_poem(poem, facts),
            ),
            frozen=True,
        )

    def _artwork_reflection(self, artwork: Artwork) -> Reflection | None:
        """Prefer the museum's own note when it's substantial — shown verbatim,
        no LLM, works even offline. Otherwise the writer composes from facts."""
        note = (artwork.curator_note or "").strip()
        if len(note) >= MIN_CURATOR_NOTE:
            return Reflection(text=note, grounded_in=[artwork.source])
        return self._reflect(
            artwork.source,
            lambda: self.wiki.facts_for(artwork),
            lambda facts: self.reflection.write(artwork, facts),
        )

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

    def _reflect(self, source: str, fetch_facts, write) -> Reflection | None:
        """Ground a reflection in real facts, returning None if the facts or the
        writer are unavailable — the reveal simply doesn't appear that day."""
        if self.wiki is None or self.reflection is None:
            return None
        try:
            facts = self._retry(fetch_facts)
            text = self._retry(lambda: write(facts))
            grounded = [source] + (["Wikipedia"] if facts.get("summary") else [])
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
