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
from .taste import TasteGate

PDB_BASE = "https://poetrydb.org"

# A solid, contemplative public-domain canon. Every name must match PoetryDB's
# /author list exactly (checked 2026-11-22): Frost, Rilke, Teasdale and Yeats aren't
# in it, so they were replaced with four poets who are.
DEFAULT_AUTHORS = (
    "Emily Dickinson", "Walt Whitman", "William Wordsworth",
    "John Keats", "Christina Rossetti", "William Blake", "Edgar Allan Poe",
    "Percy Bysshe Shelley", "Gerard Manley Hopkins", "Robert Louis Stevenson",
    "William Shakespeare", "Lord Alfred Tennyson", "Emily Bronte", "Edward Thomas",
)


class PoetrySourceError(RuntimeError):
    pass


class PoetrySource:
    def __init__(self, http: Http | None = None, authors=DEFAULT_AUTHORS,
                 max_lines: int = 30, taste_gate: Callable[[list[str]], bool] | None = None,
                 max_gate_calls: int = 5):
        self.http = http or Http()
        self.authors = tuple(authors)
        self.max_lines = max_lines
        self.gate = TasteGate(taste_gate, max_gate_calls)

    def fetch_poem(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Poem:
        authors = seeding.shuffled(seeding.seed_for(f"{date}:poet"), list(self.authors))
        last_error: Exception | None = None
        for author in authors:
            try:
                poems = self._by_author(author)
            except Exception as exc:  # noqa: BLE001 — one poet's outage must not cost the day
                last_error = exc
                continue
            short = [p for p in poems if len(p.get("lines", [])) <= self.max_lines]
            ordered = seeding.shuffled(seeding.seed_for(f"{date}:poem"), short)
            for raw in ordered:
                ref = f"{raw.get('author')}::{raw.get('title')}"
                if ref in seen:
                    continue
                if not self.gate.allows(date, ref, raw.get("lines", [])):
                    continue
                return Poem(
                    source="PoetryDB",
                    license="Public domain",
                    public_ok=True,
                    title=raw.get("title") or "Untitled",
                    author=raw.get("author") or author,
                    lines=raw.get("lines", []),
                )
        raise PoetrySourceError("no suitable poem found within length/taste constraints") from last_error

    def _by_author(self, author: str) -> list[dict]:
        url = f"{PDB_BASE}/author/{urllib.parse.quote(author)}"
        data = self.http.get_json(url)
        if isinstance(data, dict) and data.get("status"):  # PoetryDB 404 shape
            return []
        return data if isinstance(data, list) else []
