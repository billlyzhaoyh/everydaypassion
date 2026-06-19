"""MetSource — a quality-filtered artwork from The Met Open Access API.

Biases hard toward contemplation-worthy work: highlights, with images, in
visual-art departments, and always public domain (CC0). The day's choice is
deterministic via the shared seeding, and images are cached locally so we never
hotlink the live API per page view.
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from .. import seeding
from ..models import Artwork
from .http import Http

MET_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# European Paintings, Drawings & Prints, Photographs, Asian Art, The American Wing.
DEFAULT_DEPARTMENTS = (11, 9, 19, 6, 1)


class MetSourceError(RuntimeError):
    pass


class MetSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None,
                 departments=DEFAULT_DEPARTMENTS, max_probe: int = 40):
        self.image_dir = Path(image_dir)
        self.http = http or Http()
        self.departments = tuple(departments)
        self.max_probe = max_probe

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        candidates = self._candidates()
        ordered = seeding.shuffled(
            seeding.seed_for(f"{date}:artwork"),
            [c for c in candidates if str(c) not in seen] or candidates,
        )
        for obj_id in ordered[: self.max_probe]:
            obj = self.http.get_json(f"{MET_BASE}/objects/{obj_id}")
            if obj.get("isPublicDomain") and obj.get("primaryImage"):
                return self._to_artwork(obj)
        raise MetSourceError("no public-domain artwork with an image found")

    # ---- helpers --------------------------------------------------------
    def _candidates(self) -> list[int]:
        # Span every configured department and union their highlights, so a
        # date can surface a painting, photograph, or drawing — rather than
        # being locked to whichever single department a seed happened to pick.
        # `q=a` is a neutral near-universal keyword (the Met search requires
        # one); `q=painting` biased the pool toward European paintings.
        ids: list[int] = []
        for dept in self.departments:
            url = (
                f"{MET_BASE}/search?hasImages=true&isHighlight=true"
                f"&departmentId={dept}&q={urllib.parse.quote('a')}"
            )
            try:
                data = self.http.get_json(url)
            except Exception:  # noqa: BLE001 — skip a failing department, keep the rest
                continue
            ids.extend(data.get("objectIDs") or [])
        if not ids:
            raise MetSourceError("no candidates found across departments")
        return ids

    def _to_artwork(self, obj: dict) -> Artwork:
        obj_id = obj["objectID"]
        image_path = None
        try:
            small = obj.get("primaryImageSmall") or obj["primaryImage"]
            ext = Path(urllib.parse.urlparse(small).path).suffix or ".jpg"
            image_path = str(self.http.download(small, self.image_dir / f"met-{obj_id}{ext}"))
        except Exception:  # noqa: BLE001 — a missing image just means no local cache
            image_path = obj.get("primaryImageSmall") or obj.get("primaryImage")
        return Artwork(
            source="The Met",
            license="CC0",
            public_ok=True,
            title=obj.get("title") or "Untitled",
            artist=obj.get("artistDisplayName") or "Unknown",
            date=obj.get("objectDate") or "",
            medium=obj.get("medium") or "",
            ref_id=str(obj_id),
            image_path=image_path,
            artist_url=obj.get("artistWikidata_URL") or obj.get("objectWikidata_URL") or None,
        )
