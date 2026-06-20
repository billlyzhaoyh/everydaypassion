"""VamSource — artwork from the Victoria and Albert Museum, London.

Keyless API with IIIF images. Unlike the Met/AIC/Cleveland/SMK feeds, V&A images
are licensed for personal and educational use only (not CC0), so every work is
tagged ``public_ok=false`` and the source removes itself from a public build by
raising — it only enriches your private rotation.

A fine-art keyword is rotated by date (like the Met rotates departments) so the
design museum's vast decorative-object catalogue doesn't crowd out paintings.
"""

from __future__ import annotations

from pathlib import Path

from .. import seeding
from ..models import Artwork
from ._common import cache_image, pick_record
from .http import Http

SEARCH = (
    "https://api.vam.ac.uk/v2/objects/search"
    "?q={q}&images_exist=true&page_size=100&page={page}"
)
KEYWORDS = ("painting", "drawing", "watercolour", "portrait", "landscape")
LICENSE = "© Victoria and Albert Museum, London — personal use"


class VamSourceError(RuntimeError):
    pass


class VamSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None, max_page: int = 20):
        self.image_dir = Path(image_dir)
        self.http = http or Http()
        self.max_page = max_page

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        # Every V&A image is personal-use only, so it never belongs in a public build.
        if public_only:
            raise VamSourceError("V&A images are personal-use only")
        keyword = seeding.shuffled(seeding.seed_for(f"{date}:vam-q"), list(KEYWORDS))[0]
        page = seeding.seed_for(f"{date}:vam-page") % self.max_page + 1
        data = self.http.get_json(SEARCH.format(q=keyword, page=page))
        records = data.get("records") or []
        chosen = pick_record(
            date, records, seen,
            lambda r: f"va-{r['systemNumber']}",
            lambda r: (r.get("_primaryMaker") or {}).get("name"),
        )
        if chosen is None:
            raise VamSourceError("no artwork with an image found")
        iiif = (chosen.get("_images") or {}).get("_iiif_image_base_url")
        image = f"{iiif}full/!843,843/0/default.jpg" if iiif else None
        return Artwork(
            source="Victoria and Albert Museum",
            license=LICENSE,
            public_ok=False,
            title=chosen.get("_primaryTitle") or chosen.get("objectType") or "Untitled",
            artist=(chosen.get("_primaryMaker") or {}).get("name") or "Unknown",
            date=chosen.get("_primaryDate") or "",
            medium=chosen.get("objectType") or "",
            ref_id=f"va-{chosen['systemNumber']}",
            image_path=cache_image(self.http, self.image_dir, image, f"va-{chosen['systemNumber']}"),
        )
