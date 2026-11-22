"""Domain types for a single morning.

Every content item carries ``source`` / ``license`` / ``public_ok`` so a future
public build is one filter away (see PRD: publish-later readiness).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Artwork:
    source: str
    license: str
    public_ok: bool
    title: str
    artist: str
    date: str
    medium: str
    ref_id: str
    image_path: str | None = None
    artist_url: str | None = None
    # The source's own image URL, kept so a published day can re-fetch its image
    # later (the static deploy rebuilds the site without committing images).
    image_url: str | None = None
    # The museum's own publishable note about the work. When present and substantial,
    # it's shown verbatim (attributed) and the LLM is skipped entirely.
    curator_note: str = ""
    # Set when the curator note carries a different licence from the artwork
    # (e.g. AIC's ``description`` is CC BY 4.0 while the image is CC0).
    curator_note_license: str = ""
    curator_note_license_url: str = ""
    # Source-authored grounding facts (catalogue label, culture, credit line, …)
    # keyed by a human label. Used only as input to the LLM fallback when there's
    # no curator_note; museums that expose metadata populate this.
    details: dict = field(default_factory=dict)


@dataclass
class Poem:
    source: str
    license: str
    public_ok: bool
    title: str
    author: str
    lines: list[str] = field(default_factory=list)
    year: str | None = None

    @property
    def ref_id(self) -> str:
        return f"{self.author}::{self.title}"


@dataclass
class Prose:
    """A short story or essay — a 5–15 minute read, kept whole."""

    source: str
    license: str
    public_ok: bool
    title: str
    author: str
    kind: str = "story"  # "story" | "essay"
    paragraphs: list[str] = field(default_factory=list)
    word_count: int = 0
    year: str | None = None
    source_url: str | None = None

    @property
    def ref_id(self) -> str:
        return f"{self.author}::{self.title}"

    @property
    def minutes(self) -> int:
        return max(1, round(self.word_count / 230))


@dataclass
class Reflection:
    text: str
    grounded_in: list[str] = field(default_factory=list)
    license: str = ""
    license_url: str = ""


@dataclass
class DayPackage:
    date: str
    artwork: Artwork
    poem: Poem
    artwork_reflection: Reflection | None = None
    poem_reflection: Reflection | None = None
    frozen: bool = True
    # Optional extra modality; absent in older packages.
    story: Prose | None = None
    story_reflection: Reflection | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "DayPackage":
        def refl(key):
            v = d.get(key)
            return Reflection(**v) if v else None

        return DayPackage(
            date=d["date"],
            artwork=Artwork(**d["artwork"]),
            poem=Poem(**d["poem"]),
            # `reflection` is the old single-field name — read it as the artwork's.
            artwork_reflection=refl("artwork_reflection") or refl("reflection"),
            poem_reflection=refl("poem_reflection"),
            frozen=d.get("frozen", True),
            story=Prose(**d["story"]) if d.get("story") else None,
            story_reflection=refl("story_reflection"),
        )
