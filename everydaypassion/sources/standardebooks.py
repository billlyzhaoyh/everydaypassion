"""Standard Ebooks — carefully proofed public-domain books, read straight from
their GitHub repositories (no API key, no rate limit beyond GitHub's).

Each book's text is semantic XHTML: a poem is an element whose ``epub:type`` has
``z3998:poem``; a short story is an ``<article epub:type="se:short-story">`` in its
own file; the table of contents links to each. The texts are US public domain and
Standard Ebooks dedicates its own edition work to CC0, so both are publishable.

This module holds the shared reader plus the poetry source; prose sources build on
the same reader.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

from .. import seeding
from ..models import Poem, Prose
from .http import Http
from .taste import TasteGate

RAW = "https://raw.githubusercontent.com/standardebooks/{slug}/master/src/epub/{path}"
LICENSE = "Public domain (US) · Standard Ebooks edition CC0"
XHTML = "{http://www.w3.org/1999/xhtml}"
EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
DC = "{http://purl.org/dc/elements/1.1/}"
OPF = "{http://www.idpf.org/2007/opf}"
_MATTER = ("titlepage", "imprint", "colophon", "uncopyright", "halftitlepage", "dedication",
           "epigraph", "endnotes", "loi", "acknowledgements", "preface", "introduction",
           "foreword", "afterword", "appendix", "glossary", "notes")

# Collections verified to exist (raw toc.xhtml reachable, 2026-11-22). Frost and
# Yeats here cover two poets PoetryDB doesn't carry.
POETRY_COLLECTIONS = (
    "robert-frost_new-hampshire",
    "robert-frost_north-of-boston",
    "w-b-yeats_poetry",
    "john-keats_poetry",
    "walt-whitman_leaves-of-grass",
    "edward-thomas_poetry",
    "wilfred-owen_poetry",
    "langston-hughes_poetry",
)


# Short-story and essay collections, verified the same way. Long pieces are
# filtered out by word count, so collections of long essays mostly yield their
# shorter ones.
PROSE_COLLECTIONS = (
    "anton-chekhov_short-fiction_constance-garnett",
    "james-joyce_dubliners",
    "kate-chopin_short-fiction",
    "saki_short-fiction",
    "o-henry_short-fiction",
    "edgar-allan-poe_short-fiction",
    "sherwood-anderson_winesburg-ohio",
    "jack-london_short-fiction",
    "f-scott-fitzgerald_short-fiction",
    "rudyard-kipling_just-so-stories",
    "g-k-chesterton_the-innocence-of-father-brown",
    "ralph-waldo-emerson_essays",
    "henry-david-thoreau_essays",
    "washington-irving_the-sketch-book-of-geoffrey-crayon-gent",
)
_PROSE_KINDS = {"se:short-story": "story", "z3998:essay": "essay"}
GITHUB = "https://github.com/standardebooks/{slug}"


class StandardEbooksError(RuntimeError):
    pass


@dataclass(frozen=True)
class TocEntry:
    file: str      # e.g. "text/poetry.xhtml"
    anchor: str    # element id, "" when the entry is a whole file
    title: str


def text_of(el: ET.Element) -> str:
    return " ".join("".join(el.itertext()).split())


def has_type(el: ET.Element, token: str) -> bool:
    return token in (el.get(EPUB_TYPE) or "").split()


class StandardEbooksReader:
    """Fetches and parses one book's toc, metadata and text files (cached per instance)."""

    def __init__(self, http: Http | None = None):
        self.http = http or Http()
        self._cache: dict[str, ET.Element] = {}

    def _xml(self, slug: str, path: str) -> ET.Element:
        key = f"{slug}/{path}"
        if key not in self._cache:
            self._cache[key] = ET.fromstring(self.http.get_text(RAW.format(slug=slug, path=path)))
        return self._cache[key]

    def author(self, slug: str) -> str:
        creator = self._xml(slug, "content.opf").find(f"{OPF}metadata/{DC}creator")
        return text_of(creator) if creator is not None else ""

    def toc(self, slug: str) -> list[TocEntry]:
        entries, seen = [], set()
        for a in self._xml(slug, "toc.xhtml").iter(f"{XHTML}a"):
            href = a.get("href") or ""
            file, _, anchor = href.partition("#")
            name = file.rsplit("/", 1)[-1].removesuffix(".xhtml")
            if not file.startswith("text/") or name in _MATTER or href in seen:
                continue
            seen.add(href)
            entries.append(TocEntry(file, anchor, text_of(a)))
        return entries

    def element(self, slug: str, entry: TocEntry) -> ET.Element | None:
        root = self._xml(slug, entry.file)
        if entry.anchor:
            return next((el for el in root.iter() if el.get("id") == entry.anchor), None)
        body = root.find(f"{XHTML}body")
        return body.find(f"{XHTML}article") if body is not None else None


def verse_lines(el: ET.Element) -> list[str]:
    """Lines of a poem: each stanza is a <p> of <span> lines; stanzas are separated
    by "" (PoetryDB's convention). Prose paragraphs (no spans) are skipped."""
    lines: list[str] = []
    for p in el.iter(f"{XHTML}p"):
        spans = p.findall(f"{XHTML}span")
        if not spans:
            continue
        if lines:
            lines.append("")
        lines.extend(text_of(s) for s in spans)
    return lines


class StandardEbooksPoetry:
    def __init__(self, http: Http | None = None, collections=POETRY_COLLECTIONS,
                 max_lines: int = 30, min_lines: int = 4,
                 taste_gate: Callable[[list[str]], bool] | None = None,
                 max_gate_calls: int = 5, max_probe: int = 25):
        self.reader = StandardEbooksReader(http)
        self.collections = tuple(collections)
        self.max_lines, self.min_lines, self.max_probe = max_lines, min_lines, max_probe
        self.gate = TasteGate(taste_gate, max_gate_calls)

    def fetch_poem(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Poem:
        last_error: Exception | None = None
        for slug in seeding.shuffled(seeding.seed_for(f"{date}:se-poetry"), list(self.collections))[:3]:
            try:
                poem = self._from_collection(slug, date, seen)
            except Exception as exc:  # noqa: BLE001 — try the next collection
                last_error = exc
                continue
            if poem is not None:
                return poem
        raise StandardEbooksError("no suitable Standard Ebooks poem found") from last_error

    def _from_collection(self, slug: str, date: str, seen) -> Poem | None:
        author = self.reader.author(slug)
        entries = seeding.shuffled(seeding.seed_for(f"{date}:poem"), self.reader.toc(slug))
        for entry in entries[: self.max_probe]:
            el = self.reader.element(slug, entry)
            if el is None or not has_type(el, "z3998:poem"):
                continue
            lines = verse_lines(el)
            count = sum(1 for ln in lines if ln)
            if not (self.min_lines <= count <= self.max_lines):
                continue
            ref = f"{author}::{entry.title}"
            if ref in seen or not self.gate.allows(date, ref, lines):
                continue
            return Poem(source="Standard Ebooks", license=LICENSE, public_ok=True,
                        title=entry.title, author=author, lines=lines)
        return None


def prose_paragraphs(el: ET.Element) -> list[str]:
    """Body paragraphs, skipping headings/epigraph headers; verse quoted inside a
    story keeps its line breaks."""
    skip = set()
    for tag in ("header", "hgroup"):
        for h in el.iter(f"{XHTML}{tag}"):
            skip.update(id(x) for x in h.iter())
    out = []
    for p in el.iter(f"{XHTML}p"):
        if id(p) in skip:
            continue
        spans = p.findall(f"{XHTML}span")
        text = "\n".join(text_of(s) for s in spans) if spans else text_of(p)
        if text:
            out.append(text)
    return out


class StandardEbooksProse:
    def __init__(self, http: Http | None = None, collections=PROSE_COLLECTIONS,
                 min_words: int = 800, max_words: int = 3500, max_probe: int = 12):
        self.reader = StandardEbooksReader(http)
        self.collections = tuple(collections)
        self.min_words, self.max_words, self.max_probe = min_words, max_words, max_probe

    def fetch_prose(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Prose:
        last_error: Exception | None = None
        for slug in seeding.shuffled(seeding.seed_for(f"{date}:se-prose"), list(self.collections))[:3]:
            try:
                prose = self._from_collection(slug, date, seen)
            except Exception as exc:  # noqa: BLE001 — try the next collection
                last_error = exc
                continue
            if prose is not None:
                return prose
        raise StandardEbooksError("no Standard Ebooks story or essay of the right length") from last_error

    def _from_collection(self, slug: str, date: str, seen) -> Prose | None:
        author = self.reader.author(slug)
        # One entry per file: a story/essay lives in its own file (anchors inside
        # it are just its sections).
        files: dict[str, TocEntry] = {}
        for entry in self.reader.toc(slug):
            if entry.file not in files and not entry.anchor:
                files[entry.file] = entry
        entries = seeding.shuffled(seeding.seed_for(f"{date}:prose"), list(files.values()))
        for entry in entries[: self.max_probe]:
            if f"{author}::{entry.title}" in seen:
                continue
            el = self.reader.element(slug, entry)
            kind = next((k for t, k in _PROSE_KINDS.items() if el is not None and has_type(el, t)), None)
            if kind is None:
                continue
            paragraphs = prose_paragraphs(el)
            words = sum(len(p.split()) for p in paragraphs)
            if not (self.min_words <= words <= self.max_words):
                continue
            return Prose(source="Standard Ebooks", license=LICENSE, public_ok=True,
                         title=entry.title, author=author, kind=kind,
                         paragraphs=paragraphs, word_count=words,
                         source_url=GITHUB.format(slug=slug))
        return None
