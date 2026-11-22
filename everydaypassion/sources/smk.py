"""SmkSource — public-domain artwork from SMK, the National Gallery of Denmark.

Keyless API; the search endpoint returns full records filtered server-side to
public-domain works that carry an image. Since 2024 SMK marks those with the
Public Domain Mark 1.0 (no restrictions — still publishable), and its
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


# SMK credits unattributed works to "Ubekendt" (Danish: unknown).
_UNKNOWN = {"ubekendt", "unknown", "anonym"}


def _named(record: dict) -> str:
    name = _first(record.get("artist"))
    return "" if name.strip().lower() in _UNKNOWN else name


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
        chosen = pick_record(date, records, seen, lambda r: f"smk-{r['object_number']}", _named)
        if chosen is None:
            raise SmkSourceError("no public-domain artwork found")
        image = chosen.get("image_thumbnail")
        return Artwork(
            source="SMK — National Gallery of Denmark",
            license="Public Domain Mark 1.0",
            public_ok=True,
            title=_first(chosen.get("titles"), "title") or "Untitled",
            artist=_named(chosen) or "Unknown",
            date=_first(chosen.get("production_date"), "period"),
            medium=_first(chosen.get("techniques")),
            ref_id=f"smk-{chosen['object_number']}",
            image_path=cache_image(self.http, self.image_dir, image, f"smk-{chosen['object_number']}"),
            image_url=image,
        )
