"""Live health check: fetch one item from every content source and report.

    .venv/bin/python scripts/check_sources.py [DATE] [--public]

Makes real network calls (no Claude calls, nothing written except cached images
in a temp dir). Use it after changing a source, or when the morning page starts
falling back to the curated library, to see which source is failing and why.
"""

from __future__ import annotations

import argparse
import datetime
import tempfile
import time
import traceback

from everydaypassion.sources.artic import ArticSource
from everydaypassion.sources.cleveland import ClevelandSource
from everydaypassion.sources.commons import CommonsMusicSource
from everydaypassion.sources.met import MetSource
from everydaypassion.sources.poetry import PoetrySource
from everydaypassion.sources.rijks import RijksSource
from everydaypassion.sources.smk import SmkSource
from everydaypassion.sources.standardebooks import StandardEbooksPoetry, StandardEbooksProse
from everydaypassion.sources.vam import VamSource
from everydaypassion.sources.wikipedia import WikipediaClient


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("date", nargs="?", default=datetime.date.today().isoformat())
    ap.add_argument("--public", action="store_true", help="Check the public (publishable-only) path.")
    args = ap.parse_args()
    images = tempfile.mkdtemp(prefix="edp-check-")

    checks = [
        ("art", "The Met", lambda: MetSource(images).fetch_artwork(args.date, public_only=args.public)),
        ("art", "Art Institute", lambda: ArticSource(images).fetch_artwork(args.date, public_only=args.public)),
        ("art", "Cleveland", lambda: ClevelandSource(images).fetch_artwork(args.date, public_only=args.public)),
        ("art", "SMK", lambda: SmkSource(images).fetch_artwork(args.date, public_only=args.public)),
        ("art", "Rijksmuseum", lambda: RijksSource(images).fetch_artwork(args.date, public_only=args.public)),
        ("poem", "PoetryDB", lambda: PoetrySource().fetch_poem(args.date, public_only=args.public)),
        ("poem", "Standard Ebooks", lambda: StandardEbooksPoetry().fetch_poem(args.date, public_only=args.public)),
        ("story", "Standard Ebooks", lambda: StandardEbooksProse().fetch_prose(args.date, public_only=args.public)),
        ("music", "Wikimedia Commons", lambda: CommonsMusicSource().fetch_track(args.date, public_only=args.public)),
        ("facts", "Wikipedia", lambda: WikipediaClient()._lookup("John Keats")),
    ]
    if not args.public:
        checks.insert(5, ("art", "V&A", lambda: VamSource(images).fetch_artwork(args.date)))

    failures = 0
    for kind, name, fetch in checks:
        start = time.time()
        try:
            item = fetch()
        except Exception as exc:  # noqa: BLE001 — report every source
            failures += 1
            cause = f" (cause: {exc.__cause__!r})" if exc.__cause__ else ""
            print(f"FAIL  {kind:5} {name:18} {time.time() - start:5.1f}s  {exc!r}{cause}")
            if __debug__ and "-v" in __import__("sys").argv:
                traceback.print_exc()
            continue
        if isinstance(item, dict):
            label = "summary ok" if item.get("summary") else "no summary"
        else:
            who = getattr(item, "artist", None) or getattr(item, "author", "")
            label = f"{item.title[:48]} — {who[:30]}"
            if hasattr(item, "license"):
                label += f"  [{item.license}{'' if item.public_ok else ', private only'}]"
        print(f"OK    {kind:5} {name:18} {time.time() - start:5.1f}s  {label}")
    print(f"\n{len(checks) - failures}/{len(checks)} sources OK for {args.date}"
          f"{' (public)' if args.public else ''}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
