"""ReflectionWriter — Claude turns grounded facts into a short factual background note.

Feeds real museum metadata + a Wikipedia summary to Claude and asks for concise,
specific background about the work and its maker — like good museum wall text,
strictly grounded and never invented. Also exposes a taste gate the poetry source
can use to screen out doggerel.

Uses the Anthropic SDK; the client is imported lazily so the package imports
(and the core tests run) without `anthropic` installed or a key set.
"""

from __future__ import annotations

import os
import re

from ..models import Artwork, Poem, Prose, Track

DEFAULT_MODEL = os.environ.get("EVERYDAYPASSION_MODEL", "claude-opus-4-8")
# The taste gate is a one-word YES/NO screen: a small model is plenty.
DEFAULT_GATE_MODEL = os.environ.get("EVERYDAYPASSION_GATE_MODEL", "claude-haiku-5-5")
_YES = re.compile(r"\byes\b", re.IGNORECASE)

_REFLECTION_SYSTEM = (
    "You write a short, factual background note about an artwork — the kind of "
    "thing you'd read on excellent museum wall text or in a catalogue entry. Write "
    "2-3 short paragraphs (about 120-150 words) of concrete background: who the "
    "artist was and why they matter, when and where the work was made, the technique "
    "or materials, and the historical or cultural context. Lead with the most "
    "genuinely interesting or surprising fact. "
    "When curatorial notes or a catalogue description are provided, treat them as "
    "the primary, authoritative source and draw the most interesting specifics from "
    "them (rephrased, not copied verbatim). "
    "Stay strictly faithful to the facts provided — never invent biography, dates, "
    "attributions, or events; if a fact isn't given, don't assert it, and say less "
    "rather than pad. "
    "Do not address the reader ('you'), do not set a mood or mention mornings, "
    "rituals, or contemplation, and avoid generic art-criticism filler "
    "('masterpiece', 'timeless', 'invites the viewer', 'captures the essence'). "
    "Plain, precise, informative. Output only the note, with no preamble, title, "
    "or sign-off."
)

_POEM_SYSTEM = (
    "You write a short, factual background note about a poem and its poet — the kind "
    "of thing you'd read in a good anthology's notes. Given the poem text and real "
    "facts about the poet, write 2-3 short paragraphs (about 120-150 words): who the "
    "poet was and why they matter, when and in what context the poem was written if "
    "the facts support it, its form or notable features, and what it is about. Lead "
    "with the most genuinely interesting fact. "
    "Stay strictly faithful to the facts provided — never invent biography or dates; "
    "if a fact isn't given, don't assert it. "
    "Do not address the reader ('you'), do not set a mood or mention mornings, "
    "rituals, or contemplation, and avoid generic praise ('timeless', 'hauntingly "
    "beautiful', 'speaks to the soul'). Plain, precise, informative. Output only the "
    "note, with no preamble, title, or sign-off."
)

_PROSE_SYSTEM = (
    "You write a short, factual background note about a short story or essay and its "
    "author — the kind of thing you'd read in a good anthology's notes. Given the "
    "opening of the text and real facts about the author, write 2-3 short paragraphs "
    "(about 120-150 words): who the author was and why they matter, when and in what "
    "context the piece was written if the facts support it, and what it is about — "
    "without spoiling its ending. Lead with the most genuinely interesting fact. "
    "Stay strictly faithful to the facts provided — never invent biography or dates; "
    "if a fact isn't given, don't assert it. "
    "Do not address the reader ('you'), do not set a mood or mention mornings, "
    "rituals, or contemplation, and avoid generic praise. Plain, precise, informative. "
    "Output only the note, with no preamble, title, or sign-off."
)

_MUSIC_SYSTEM = (
    "You write a short, factual background note about a piece of music and its "
    "composer — the kind of thing you'd read in good concert programme notes. Given "
    "the recording's title, credits and description, and real facts about the "
    "composer, write 2-3 short paragraphs (about 120-150 words): who the composer was "
    "and why they matter, when and why the piece was written if the facts support it, "
    "and its form or what to listen for. Lead with the most genuinely interesting fact. "
    "Stay strictly faithful to the facts provided — never invent biography, dates or "
    "musical details; if a fact isn't given, don't assert it. "
    "Do not address the reader ('you'), do not set a mood or mention mornings, "
    "rituals, or contemplation, and avoid generic praise. Plain, precise, informative. "
    "Output only the note, with no preamble, title, or sign-off."
)

_TASTE_SYSTEM = (
    "You screen public-domain poems for a contemplative morning ritual. A poem "
    "passes only if it is genuinely well-crafted and rewards a quiet sit — not "
    "doggerel, greeting-card verse, or a dated, plodding piece. Answer with a single "
    "word: YES if it passes, NO if it does not."
)


class ReflectionWriter:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, api_key: str | None = None,
                 gate_model: str = DEFAULT_GATE_MODEL):
        self.model = model
        self.gate_model = gate_model
        self._client = client
        self._api_key = api_key

    def write(self, artwork: Artwork, facts: dict) -> str:
        summary = (facts or {}).get("summary", "").strip()
        details = [
            f"Title: {artwork.title}",
            f"Artist: {artwork.artist}",
            f"Date: {artwork.date}",
            f"Medium: {artwork.medium}",
            f"Source: {artwork.source}",
        ]
        for label, value in (artwork.details or {}).items():
            details.append(f"{label}: {value}")
        if summary:
            details.append(f"\nAbout the artist (from Wikipedia):\n{summary}")
        prompt = (
            "Write the background note from these facts:\n\n" + "\n".join(details)
        )
        resp = self._messages().create(
            model=self.model,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_REFLECTION_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._text(resp)

    def write_poem(self, poem: Poem, facts: dict) -> str:
        summary = (facts or {}).get("summary", "").strip()
        details = [f"Poem: {poem.title}", f"Poet: {poem.author}", "", "\n".join(poem.lines)]
        if summary:
            details.append(f"\nAbout the poet (from Wikipedia):\n{summary}")
        prompt = "Write the background note from this poem and these facts:\n\n" + "\n".join(details)
        resp = self._messages().create(
            model=self.model,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_POEM_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._text(resp)

    def write_prose(self, prose: Prose, facts: dict) -> str:
        summary = (facts or {}).get("summary", "").strip()
        opening = "\n\n".join(prose.paragraphs[:6])
        details = [f"{prose.kind.title()}: {prose.title}", f"Author: {prose.author}",
                   "", f"Opening:\n{opening}"]
        if summary:
            details.append(f"\nAbout the author (from Wikipedia):\n{summary}")
        prompt = "Write the background note from this text and these facts:\n\n" + "\n".join(details)
        resp = self._messages().create(
            model=self.model,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_PROSE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._text(resp)

    def write_music(self, track: Track, facts: dict) -> str:
        summary = (facts or {}).get("summary", "").strip()
        details = [f"Recording: {track.title}", f"Credits: {track.artist}"]
        if track.year:
            details.append(f"Date: {track.year}")
        if track.description:
            details.append(f"Description: {track.description}")
        if summary:
            details.append(f"\nAbout the composer (from Wikipedia):\n{summary}")
        prompt = "Write the background note from these facts:\n\n" + "\n".join(details)
        resp = self._messages().create(
            model=self.model,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_MUSIC_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._text(resp)

    def taste_ok(self, lines: list[str]) -> bool:
        poem = "\n".join(lines).strip()
        resp = self._messages().create(
            model=self.gate_model,
            max_tokens=16,
            # Thinking off so the tiny budget goes to the one-word answer.
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            system=_TASTE_SYSTEM,
            messages=[{"role": "user", "content": poem}],
        )
        # Tolerate "Yes.", "**YES**" etc.
        return bool(_YES.search(self._text(resp)))

    # ---- helpers --------------------------------------------------------
    def _messages(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client.messages

    @staticmethod
    def _text(resp) -> str:
        return next((b.text for b in resp.content if b.type == "text"), "").strip()
