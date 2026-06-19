"""ReflectionWriter — Claude turns grounded facts into a short morning reflection.

Feeds real Met metadata + a Wikipedia summary to Claude and asks for a warm,
accurate 2-3 paragraph reflection — grounded, never invented. Also exposes a
taste gate the poetry source can use to screen out doggerel.

Uses the Anthropic SDK; the client is imported lazily so the package imports
(and the core tests run) without `anthropic` installed or a key set.
"""

from __future__ import annotations

import os

from ..models import Artwork

DEFAULT_MODEL = os.environ.get("EVERYDAYPASSION_MODEL", "claude-opus-4-8")

_REFLECTION_SYSTEM = (
    "You write short morning reflections for a personal art-and-poetry ritual. "
    "Given real facts about an artwork and its artist, write 2-3 short paragraphs "
    "(about 120 words) that are warm, grounded, and contemplative. Stay strictly "
    "faithful to the facts provided — never invent biography, dates, or events. If "
    "a fact isn't given, don't assert it. Output only the reflection prose, with no "
    "preamble, title, or sign-off."
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
            "Write the reflection from these facts:\n\n" + "\n".join(details)
        )
        resp = self._messages().create(
            model=self.model,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_REFLECTION_SYSTEM,
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
