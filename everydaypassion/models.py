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
class Reflection:
    text: str
    grounded_in: list[str] = field(default_factory=list)


@dataclass
class DayPackage:
    date: str
    artwork: Artwork
    poem: Poem
    artwork_reflection: Reflection | None = None
    poem_reflection: Reflection | None = None
    frozen: bool = True

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
        )
