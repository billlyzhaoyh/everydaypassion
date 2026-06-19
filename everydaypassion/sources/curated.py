"""Curated modern sources — your private library of contemporary art and poems.

Modern/contemporary work is copyrighted (no free firehose, same as the museum
APIs and PoetryDB), so it lives in a hand-curated set tagged `public_ok: false`
and is surfaced as a first-class source in the daily rotation. Images for modern
art are dropped into the served images directory and referenced by filename.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import seeding
from ..models import Artwork, Poem


def _load(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class CuratedModernArt:
    def __init__(self, root: str | Path, images_dir: str | Path):
        self.path = Path(root) / "artworks_modern.json"
        self.images = Path(images_dir)

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        arts = [Artwork(**a) for a in _load(self.path)]
        if public_only:
            arts = [a for a in arts if a.public_ok]
        avail = [a for a in arts if a.ref_id not in seen] or arts
        if not avail:
            raise LookupError("no curated modern artworks")
        chosen = seeding.shuffled(seeding.seed_for(f"{date}:artwork"), avail)[0]
        # A bare filename resolves to the served images directory.
        if chosen.image_path and not Path(chosen.image_path).is_absolute():
            chosen.image_path = str(self.images / chosen.image_path)
        return chosen


class CuratedModernPoems:
    def __init__(self, root: str | Path):
        self.path = Path(root) / "poems_modern.json"

    def fetch_poem(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Poem:
        poems = [Poem(**p) for p in _load(self.path)]
        if public_only:
            poems = [p for p in poems if p.public_ok]
        avail = [p for p in poems if p.ref_id not in seen] or poems
        if not avail:
            raise LookupError("no curated modern poems")
        return seeding.shuffled(seeding.seed_for(f"{date}:poem"), avail)[0]
