"""PoetrySource — a short, well-crafted public-domain poem from PoetryDB.

Constrains length (no epics), draws from a canon allowlist, and runs each
candidate past an optional taste gate (a callable taking the poem's lines and
returning True to keep) so doggerel and dated filler get screened out.
"""

from __future__ import annotations

import urllib.parse
from typing import Callable

from .. import seeding
from ..models import Poem
from .http import Http

PDB_BASE = "https://poetrydb.org"

# A solid, contemplative public-domain canon. Widen freely over time.
DEFAULT_AUTHORS = (
    "Emily Dickinson", "Robert Frost", "Walt Whitman", "William Wordsworth",
    "John Keats", "Christina Rossetti", "William Blake", "Edgar Allan Poe",
    "Percy Bysshe Shelley", "Sara Teasdale", "Rainer Maria Rilke",
    "William Butler Yeats", "Gerard Manley Hopkins", "Robert Louis Stevenson",
)


class PoetrySourceError(RuntimeError):
    pass


class PoetrySource:
    def __init__(self, http: Http | None = None, authors=DEFAULT_AUTHORS,
                 max_lines: int = 30, taste_gate: Callable[[list[str]], bool] | None = None):
        self.http = http or Http()
        self.authors = tuple(authors)
        self.max_lines = max_lines
        self.taste_gate = taste_gate

    def fetch_poem(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Poem:
        authors = seeding.shuffled(seeding.seed_for(f"{date}:poet"), list(self.authors))
        for author in authors:
            poems = self._by_author(author)
            short = [p for p in poems if len(p.get("lines", [])) <= self.max_lines]
            ordered = seeding.shuffled(seeding.seed_for(f"{date}:poem"), short)
            for raw in ordered:
                ref = f"{raw.get('author')}::{raw.get('title')}"
                if ref in seen:
                    continue
                lines = [ln for ln in raw.get("lines", []) if ln.strip() != ""] or raw.get("lines", [])
                if not self._tasteful(lines):
                    continue
                return Poem(
                    source="PoetryDB",
                    license="Public domain",
                    public_ok=True,
                    title=raw.get("title") or "Untitled",
                    author=raw.get("author") or author,
                    lines=raw.get("lines", []),
                )
        raise PoetrySourceError("no suitable poem found within length/taste constraints")

    def _tasteful(self, lines: list[str]) -> bool:
        if self.taste_gate is None:
            return True
        try:
            return bool(self.taste_gate(lines))
        except Exception:  # noqa: BLE001 — a broken screener must not cost the poem
            return True

    def _by_author(self, author: str) -> list[dict]:
        url = f"{PDB_BASE}/author/{urllib.parse.quote(author)}"
        data = self.http.get_json(url)
        if isinstance(data, dict) and data.get("status"):  # PoetryDB 404 shape
            return []
        return data if isinstance(data, list) else []
