"""SourcePool — rotate across several sources by date, falling through on failure.

Each source gets an equal shot per day (the choice is seeded by the date), and
if the chosen one errors — offline, rate-limited, empty curated set — the pool
falls through to the next. Implements both fetch_artwork and fetch_poem; only
the relevant one is ever called.
"""

from __future__ import annotations

from .. import seeding


class SourcePool:
    def __init__(self, sources: list, kind: str):
        self.sources = list(sources)
        self.kind = kind  # "art" or "poem" — also seeds the rotation

    def fetch_artwork(self, date: str, seen=frozenset(), public_only: bool = False):
        return self._fetch("fetch_artwork", date, seen, public_only)

    def fetch_poem(self, date: str, seen=frozenset(), public_only: bool = False):
        return self._fetch("fetch_poem", date, seen, public_only)

    def _fetch(self, method: str, date: str, seen, public_only: bool):
        ordered = seeding.shuffled(seeding.seed_for(f"{date}:{self.kind}-source"), self.sources)
        last: Exception | None = None
        for source in ordered:
            try:
                return getattr(source, method)(date=date, seen=seen, public_only=public_only)
            except Exception as exc:  # noqa: BLE001 — try the next source
                last = exc
        raise last or RuntimeError(f"no {self.kind} source produced a result")
