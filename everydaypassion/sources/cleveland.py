"""ClevelandSource — CC0 artwork from the Cleveland Museum of Art.

Keyless API; `cc0=1&has_image=1` returns full CC0 records with images.
"""

from __future__ import annotations

from pathlib import Path

from .. import seeding
from ..models import Artwork
from ._common import cache_image, pick_record
from .http import Http

SEARCH = "https://openaccess-api.clevelandart.org/api/artworks/?cc0=1&has_image=1&limit=100&skip={skip}"


class ClevelandSourceError(RuntimeError):
    pass


def _artist(record: dict) -> str:
    creators = record.get("creators") or []
    if not creators:
        return ""
    # e.g. "George Bellows (American, 1882–1925)" -> "George Bellows"
    return (creators[0].get("description") or "").split(" (")[0].strip()


class ClevelandSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None, max_skip: int = 400):
        self.image_dir = Path(image_dir)
        self.http = http or Http()
        self.max_skip = max_skip

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        skip = (seeding.seed_for(f"{date}:cma-page") % self.max_skip) * 100
        data = self.http.get_json(SEARCH.format(skip=skip))
        records = data.get("data") or []
        chosen = pick_record(date, records, seen, lambda r: f"cma-{r['id']}", _artist)
        if chosen is None:
            raise ClevelandSourceError("no CC0 artwork found")
        image = ((chosen.get("images") or {}).get("web") or {}).get("url")
        return Artwork(
            source="Cleveland Museum of Art",
            license="CC0",
            public_ok=True,
            title=chosen.get("title") or "Untitled",
            artist=_artist(chosen) or "Unknown",
            date=chosen.get("creation_date") or "",
            medium=chosen.get("technique") or "",
            ref_id=f"cma-{chosen['id']}",
            image_path=cache_image(self.http, self.image_dir, image, f"cma-{chosen['id']}"),
        )
