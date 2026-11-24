"""RijksSource — public-domain paintings from the Rijksmuseum, Amsterdam.

Keyless Linked Art APIs (the old key-based collection API is being retired):
``data.rijksmuseum.nl/search/collection`` returns object IDs (100 per page, cursor
paging), and ``data.rijksmuseum.nl/<id>`` resolves one object as Linked Art JSON-LD
with an English title, creator statement, medium, a IIIF image and — per image — a
rights URI. Some paintings are "In Copyright", so only images marked CC0 or Public
Domain Mark are taken.

The search can't jump to a random page, so the day's draw is spread by filtering
on a date-seeded decade of creation (``creationDate=165*``) instead.
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import seeding
from ..models import Artwork
from ._common import cache_image
from .http import Http

BASE = "https://data.rijksmuseum.nl"
SEARCH = BASE + "/search/collection?type=painting&imageAvailable=true"
LD_JSON = {"Accept": "application/ld+json"}

ENGLISH = "300388277"  # AAT: English
_AAT = {"creator": "300435416", "medium": "300435429", "dimensions": "300435430",
        "credit": "300026687", "accession": "300312355"}
RIGHTS = {
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0",
    "https://creativecommons.org/publicdomain/mark/1.0/": "Public Domain Mark 1.0",
}
# Decades with a solid run of paintings; the rights check filters the rest.
DECADES = tuple(f"{d}*" for d in range(150, 192))


class RijksSourceError(RuntimeError):
    pass


def _english(items, aat: str | None = None) -> str:
    """The first English ``content`` among Linked Art statements/names, optionally
    restricted to one AAT classification."""
    fallback = ""
    for it in items or []:
        if aat and not any(c.get("id", "").endswith(aat) for c in it.get("classified_as", [])):
            continue
        content = it.get("content") or ""
        if any(lang.get("id", "").endswith(ENGLISH) for lang in it.get("language", [])):
            return content
        fallback = fallback or content
    return fallback


def _image_and_rights(obj: dict) -> tuple[str | None, str | None]:
    for subject in obj.get("subject_of", []):
        for carrier in subject.get("digitally_carried_by", []):
            urls = [a.get("id") for a in carrier.get("access_point", []) if a.get("id")]
            rights = [r.get("content") for r in carrier.get("referred_to_by", [])]
            if urls:
                return urls[0], next((r for r in rights if r), None)
    return None, None


def _person(obj: dict) -> tuple[str, str | None]:
    """The first named maker (English notation) and their Wikidata URL, if any."""
    for part in obj.get("produced_by", {}).get("part", []):
        for who in part.get("carried_out_by", []):
            names = [n.get("@value") for n in who.get("notation", []) if n.get("@language") == "en"]
            wikidata = next((e["id"] for e in who.get("equivalent", [])
                             if "wikidata.org" in e.get("id", "")), None)
            if names and names[0]:
                return names[0], wikidata
    return "", None


class RijksSource:
    def __init__(self, image_dir: str | Path, http: Http | None = None, max_probe: int = 8):
        self.image_dir = Path(image_dir)
        self.http = http or Http(extra_headers=LD_JSON)
        self.max_probe = max_probe

    def fetch_artwork(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Artwork:
        decade = seeding.shuffled(seeding.seed_for(f"{date}:rijks-decade"), list(DECADES))[0]
        page = self.http.get_json(f"{SEARCH}&creationDate={decade}")
        ids = [i["id"].rsplit("/", 1)[-1] for i in page.get("orderedItems") or []]
        if not ids:
            page = self.http.get_json(SEARCH)
            ids = [i["id"].rsplit("/", 1)[-1] for i in page.get("orderedItems") or []]
        pool = [i for i in ids if f"rijks-{i}" not in seen] or ids
        fallback: Artwork | None = None
        for oid in seeding.shuffled(seeding.seed_for(f"{date}:artwork"), pool)[: self.max_probe]:
            obj = self.http.get_json(f"{BASE}/{oid}")
            image, rights = _image_and_rights(obj)
            if not image or rights not in RIGHTS:
                continue  # no image, or not free to publish (e.g. In Copyright)
            statement = _english(obj.get("produced_by", {}).get("referred_to_by"), _AAT["creator"])
            named = bool(statement) and "anonymous" not in statement.lower()
            if named:
                return self._to_artwork(oid, obj, image, rights, statement)
            fallback = fallback or (oid, obj, image, rights, statement)
        if fallback is not None:
            return self._to_artwork(*fallback)
        raise RijksSourceError("no public-domain painting with an image found")

    def _to_artwork(self, oid: str, obj: dict, image: str, rights: str, statement: str) -> Artwork:
        person, wikidata = _person(obj)
        anonymous = not statement or "anonymous" in statement.lower()
        sized = image.replace("/full/max/", "/full/843,/")
        title = _english([n for n in obj.get("identified_by", []) if n.get("type") == "Name"])
        produced = obj.get("produced_by", {})
        date = _english(produced.get("timespan", {}).get("identified_by"))
        details = {
            "Object number": _english(obj.get("identified_by"), _AAT["accession"]),
            "Creator statement": statement,
            "Dimensions": _english(obj.get("referred_to_by"), _AAT["dimensions"]),
            "Credit line": _english(obj.get("referred_to_by"), _AAT["credit"]),
        }
        return Artwork(
            source="Rijksmuseum",
            license=RIGHTS[rights],
            public_ok=True,
            title=title or "Untitled",
            # Prefer the clean person name (good for Wikipedia); keep the statement
            # ("copy after …") when there's no named person.
            artist="Unknown" if anonymous else (person or re.sub(r"\s*\([^)]*\)$", "", statement)),
            date=date,
            medium=_english(obj.get("referred_to_by"), _AAT["medium"]),
            ref_id=f"rijks-{oid}",
            image_path=cache_image(self.http, self.image_dir, sized, f"rijks-{oid}"),
            image_url=sized,
            artist_url=wikidata,
            details={k: v for k, v in details.items() if v},
        )
