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

# A solid, contemplative public-domain canon. Every name must exist in PoetryDB
# (check https://poetrydb.org/author before adding one): Frost, Rilke, Teasdale and
# Yeats were dropped after 156 published days yielded no PoetryDB poem by any of them.
DEFAULT_AUTHORS = (
    "Emily Dickinson", "Walt Whitman", "William Wordsworth",
    "John Keats", "Christina Rossetti", "William Blake", "Edgar Allan Poe",
    "Percy Bysshe Shelley", "Gerard Manley Hopkins", "Robert Louis Stevenson",
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
        self.taste_gate = taste_gate
        # Each gate call is a model request: cap them per fetch, and remember
        # verdicts so a retry or rebuild doesn't pay (or re-roll) them again.
        self.max_gate_calls = max_gate_calls
        self._verdicts: dict[str, bool] = {}
        self._gate_spent: dict[str, int] = {}  # per date, so a retry resumes the budget

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
                verdict = self._verdicts.get(ref)
                spent = self._gate_spent.get(date, 0)
                if verdict is None and self.taste_gate is not None and spent < self.max_gate_calls:
                    self._gate_spent[date] = spent + 1
                    lines = [ln for ln in raw.get("lines", []) if ln.strip() != ""] or raw.get("lines", [])
                    verdict = self._verdicts[ref] = self._tasteful(lines)
                if verdict is False:
                    continue
                # No gate, gate budget spent, or a pass: take it.
                return Poem(
                    source="PoetryDB",
                    license="Public domain",
                    public_ok=True,
                    title=raw.get("title") or "Untitled",
                    author=raw.get("author") or author,
                    lines=raw.get("lines", []),
                )
        raise PoetrySourceError("no suitable poem found within length/taste constraints") from last_error

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
