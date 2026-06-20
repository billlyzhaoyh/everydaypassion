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

from ..models import Artwork, Poem

DEFAULT_MODEL = os.environ.get("EVERYDAYPASSION_MODEL", "claude-opus-4-8")

_REFLECTION_SYSTEM = (
    "You write a short, factual background note about an artwork — the kind of "
    "thing you'd read on excellent museum wall text or in a catalogue entry. Given "
    "real facts about the work and its artist, write 2-3 short paragraphs (about "
    "120-150 words) of concrete background: who the artist was and why they matter, "
    "when and where the work was made, the technique or materials, and the "
    "historical or cultural context. Lead with the most genuinely interesting or "
    "surprising fact. "
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

_TASTE_SYSTEM = (
    "You screen public-domain poems for a contemplative morning ritual. A poem "
    "passes only if it is genuinely well-crafted and rewards a quiet sit — not "
    "doggerel, greeting-card verse, or a dated, plodding piece. Answer with a single "
    "word: YES if it passes, NO if it does not."
)


class ReflectionWriter:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, api_key: str | None = None):
        self.model = model
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
        if summary:
            details.append(f"\nBackground (from Wikipedia):\n{summary}")
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

    def taste_ok(self, lines: list[str]) -> bool:
        poem = "\n".join(lines).strip()
        resp = self._messages().create(
            model=self.model,
            max_tokens=8,
            output_config={"effort": "low"},
            system=_TASTE_SYSTEM,
            messages=[{"role": "user", "content": poem}],
        )
        return self._text(resp).strip().lower().startswith("y")

    # ---- helpers --------------------------------------------------------
    def _messages(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client.messages

    @staticmethod
    def _text(resp) -> str:
        return next((b.text for b in resp.content if b.type == "text"), "").strip()
