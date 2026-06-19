"""SmkSource — public-domain artwork from SMK, the National Gallery of Denmark.

Keyless API; the search endpoint returns full records filtered server-side to
public-domain works that carry an image. SMK releases those under CC0, and its
`image_thumbnail` is a ready-to-use IIIF URL (max 1024px) — no per-object probe.
"""

from __future__ import annotations

from pathlib import Path

from .. import seeding
from ..models import Artwork
from ._common import cache_image, pick_record
from .http import Http

SEARCH = (
    "https://api.smk.dk/api/v1/art/search/"
    "?keys=*&filters=%5Bhas_image%3Atrue%5D%2C%5Bpublic_domain%3Atrue%5D"
    "&offset={offset}&rows=100"
)


class SmkSourceError(RuntimeError):
    pass


def _first(value, key=None):
    if not value:
        return ""
    item = value[0]
    return (item.get(key) if key else item) or ""


class SmkSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None, max_page: int = 390):
        self.image_dir = Path(image_dir)
        self.http = http or Http()
        self.max_page = max_page

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        offset = (seeding.seed_for(f"{date}:smk-page") % self.max_page) * 100
        data = self.http.get_json(SEARCH.format(offset=offset))
        records = data.get("items") or []
        chosen = pick_record(date, records, seen, lambda r: f"smk-{r['object_number']}", lambda r: r.get("artist"))
        if chosen is None:
            raise SmkSourceError("no public-domain artwork found")
        return Artwork(
            source="SMK — National Gallery of Denmark",
            license="CC0",
            public_ok=True,
            title=_first(chosen.get("titles"), "title") or "Untitled",
            artist=_first(chosen.get("artist")) or "Unknown",
            date=_first(chosen.get("production_date"), "period"),
            medium=_first(chosen.get("techniques")),
            ref_id=f"smk-{chosen['object_number']}",
            image_path=cache_image(self.http, self.image_dir, chosen.get("image_thumbnail"), f"smk-{chosen['object_number']}"),
        )
