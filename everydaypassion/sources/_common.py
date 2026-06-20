"""Shared helpers for museum artwork sources."""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from .. import seeding


def pick_record(date: str, records: list, seen, ref, is_named):
    """Deterministically choose a record for ``date``, excluding anything in
    ``seen`` and preferring one with a named artist. Returns None if empty.

    ``ref(r)`` yields the record's id; ``is_named(r)`` is truthy when it has a
    real artist — so the "about the artist" reflection has someone to ground on.
    """
    pool = [r for r in records if str(ref(r)) not in seen] or list(records)
    fallback = None
    for r in seeding.shuffled(seeding.seed_for(f"{date}:artwork"), pool):
        if fallback is None:
            fallback = r
        if is_named(r):
            return r
    return fallback


def cache_image(http, images_dir, url: str | None, name: str) -> str | None:
    """Download an image locally so we never hotlink per page view; fall back
    to the remote URL if the download fails, and None if there's no URL."""
    if not url:
        return None
    try:
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
        return str(http.download(url, Path(images_dir) / f"{name}{ext}"))
    except Exception:  # noqa: BLE001 — a failed cache just falls back to the URL
        return url
