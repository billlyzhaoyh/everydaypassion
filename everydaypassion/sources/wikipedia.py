"""WikipediaClient — factual grounding for the reflection.

Returns a plain-text summary for the artist (preferred) or the work, via the
free Wikipedia REST summary endpoint. The reflection writer turns these *facts*
into prose, so we never republish Wikipedia text verbatim.
"""

from __future__ import annotations

import urllib.parse

from ..models import Artwork
from .http import Http

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"


class WikipediaClient:
    def __init__(self, http: Http | None = None):
        self.http = http or Http()

    def facts_for(self, artwork: Artwork) -> dict:
        for term in (artwork.artist, artwork.title):
            if not term or term == "Unknown":
                continue
            try:
                data = self.http.get_json(WIKI_SUMMARY + urllib.parse.quote(term.replace(" ", "_")))
            except Exception:  # noqa: BLE001 — try the next term, then give up gracefully
                continue
            extract = data.get("extract")
            if extract:
                return {"term": term, "summary": extract}
        return {"term": "", "summary": ""}
