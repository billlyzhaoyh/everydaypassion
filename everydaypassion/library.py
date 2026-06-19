"""CuratedLibrary — the local, on-disk corpus.

Holds curated modern poems (copyrighted → ``public_ok = False``, private only)
plus public-domain fallback poems and artworks. Doubles as the offline / outage
safety net: when a live source fails, DayBuilder draws from here so the ritual
always renders.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Artwork, Poem
from .seeding import seed_for, shuffled


class CuratedLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def poems(self, public_only: bool = False) -> list[Poem]:
        items = [Poem(**p) for p in self._load("poems.json")]
        return [p for p in items if p.public_ok] if public_only else items

    def artworks(self, public_only: bool = False) -> list[Artwork]:
        items = [Artwork(**a) for a in self._load("artworks.json")]
        return [a for a in items if a.public_ok] if public_only else items

    def get_poem(self, key: str, public_only: bool = False) -> Poem:
        return self._pick(key, self.poems(public_only), "no curated poems available")

    def get_artwork(self, key: str, public_only: bool = False) -> Artwork:
        return self._pick(key, self.artworks(public_only), "no curated artworks available")

    # ---- helpers --------------------------------------------------------
    def _load(self, name: str) -> list:
        path = self.root / name
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _pick(key: str, pool: list, err: str):
        if not pool:
            raise LookupError(err)
        idx = shuffled(seed_for(key), list(range(len(pool))))[0]
        return pool[idx]
