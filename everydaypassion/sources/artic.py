"""ArticSource — public-domain artwork from the Art Institute of Chicago.

Keyless API; the search endpoint returns full records (no per-object probe),
filtered server-side to public-domain works that have an image. CC0.
"""

from __future__ import annotations

from pathlib import Path

from .. import seeding
from ..models import Artwork
from ._common import cache_image, clean_text, details_from, pick_record
from .http import Http

SEARCH = (
    "https://api.artic.edu/api/v1/artworks/search"
    "?query[bool][must][][term][is_public_domain]=true"
    "&query[bool][must][][exists][field]=image_id"
    "&fields=id,title,artist_title,date_display,medium_display,image_id"
    ",short_description,description,place_of_origin,credit_line"
    "&limit=100&page={page}"
)

# The Art Institute writes its own gallery text — use it as the primary grounding.
_DETAILS = {
    "Curator's summary": "short_description",
    "Curatorial description": "description",
    "Place of origin": "place_of_origin",
    "Credit line": "credit_line",
}
DEFAULT_IIIF = "https://www.artic.edu/iiif/2"
# AIC asks clients to identify themselves; deep paging past 10k results is rejected.
AIC_UA = {"AIC-User-Agent": "everydaypassion (personal morning ritual)"}


class ArticSourceError(RuntimeError):
    pass


class ArticSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None, max_page: int = 100):
        self.image_dir = Path(image_dir)
        self.http = http or Http(extra_headers=AIC_UA)
        self.max_page = max_page  # page*limit must stay within AIC's 10,000-result window

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        page = seeding.seed_for(f"{date}:artic-page") % self.max_page + 1
        data = self.http.get_json(SEARCH.format(page=page))
        records = data.get("data") or []
        chosen = pick_record(date, records, seen, lambda r: f"artic-{r['id']}", lambda r: r.get("artist_title"))
        if chosen is None:
            raise ArticSourceError("no public-domain artwork found")
        iiif = (data.get("config") or {}).get("iiif_url", DEFAULT_IIIF)
        image = f"{iiif}/{chosen['image_id']}/full/843,/0/default.jpg"
        return Artwork(
            source="Art Institute of Chicago",
            license="CC0",
            public_ok=True,
            title=chosen.get("title") or "Untitled",
            artist=chosen.get("artist_title") or "Unknown",
            date=chosen.get("date_display") or "",
            medium=chosen.get("medium_display") or "",
            ref_id=f"artic-{chosen['id']}",
            image_path=cache_image(self.http, self.image_dir, image, f"artic-{chosen['id']}"),
            curator_note=clean_text(chosen.get("description")) or clean_text(chosen.get("short_description")),
            details=details_from(chosen, _DETAILS),
        )
