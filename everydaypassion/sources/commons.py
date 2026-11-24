"""CommonsMusicSource — freely licensed recordings from Wikimedia Commons.

One API request per build: the files of a date-seeded category, with each file's
licence and credits (``extmetadata``). Audio is never downloaded or committed —
the page streams it from Wikimedia (``preload="none"``), preferring Commons' MP3
transcode for Ogg/FLAC originals so Safari can play it.

A recording is only free if both the composition and the performance are; Commons'
per-file licence covers the recording. What's publishable is decided per category:
"Public domain" counts only where the rights holder dedicated the recordings
(Musopen's Set Chopin Free); elsewhere such claims often rest on non-US rules (EU
recording terms), so those categories stay private-only.
"""

from __future__ import annotations

import re
import urllib.parse

from .. import seeding
from ..models import Track
from .http import Http

API = "https://commons.wikimedia.org/w/api.php"
# Category -> licences publishable on the public site (None: private only).
# Checked on Commons 2026-11-22: Open Goldberg = 31 CC0 tracks; Set Chopin Free =
# 155 tracks, all "Public domain" (Musopen's dedication); Musopen = mixed sources.
CATEGORIES = {
    "Open_Goldberg_Variations": {"CC0"},
    "Set_Chopin_Free": {"CC0", "Public domain"},
    "Musopen": None,
}
PRIVATE_LICENSES = {"CC0", "Public domain"}
_TRANSCODE = {".ogg", ".oga", ".flac", ".wav", ".opus"}
_TAG = re.compile(r"<[^>]+>")


class CommonsMusicError(RuntimeError):
    pass


def _plain(value: str | None) -> str:
    return " ".join(_TAG.sub(" ", value or "").split())


def _meta(info: dict, key: str) -> str:
    return _plain((info.get("extmetadata") or {}).get(key, {}).get("value"))


def mp3_transcode(url: str) -> str | None:
    """Commons' MP3 transcode of an Ogg/FLAC original:
    .../commons/a/ab/Name.ogg -> .../commons/transcoded/a/ab/Name.ogg/Name.ogg.mp3"""
    parts = urllib.parse.urlsplit(url)
    path = parts.path
    if "/wikipedia/commons/" not in path or "/transcoded/" in path:
        return None
    if not any(path.lower().endswith(ext) for ext in _TRANSCODE):
        return None
    name = path.rsplit("/", 1)[-1]
    path = path.replace("/wikipedia/commons/", "/wikipedia/commons/transcoded/", 1) + f"/{name}.mp3"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class CommonsMusicSource:
    def __init__(self, http: Http | None = None, categories: dict | None = None):
        self.http = http or Http()
        self.categories = dict(CATEGORIES if categories is None else categories)

    def fetch_track(self, date: str, seen: set[str] = frozenset(), public_only: bool = False) -> Track:
        names = [c for c, lic in self.categories.items() if lic or not public_only]
        if not names:
            raise CommonsMusicError("no publishable music categories configured")
        category = seeding.shuffled(seeding.seed_for(f"{date}:music-category"), names)[0]
        publishable = self.categories[category] or set()
        query = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "categorymembers", "gcmtitle": f"Category:{category}",
            "gcmtype": "file", "gcmlimit": "500",
            "prop": "imageinfo", "iiprop": "url|extmetadata|mediatype",
            "iiextmetadatafilter": "LicenseShortName|Artist|ObjectName|DateTimeOriginal|ImageDescription",
        })
        data = self.http.get_json(f"{API}?{query}")
        allowed = publishable if public_only else PRIVATE_LICENSES
        candidates = []
        for page in (data.get("query") or {}).get("pages") or []:
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mediatype") != "AUDIO" or _meta(info, "LicenseShortName") not in allowed:
                continue
            candidates.append((page, info))
        pool = [c for c in candidates if f"commons-{c[0]['pageid']}" not in seen] or candidates
        if not pool:
            raise CommonsMusicError(f"no freely licensed audio in Category:{category}")
        pool.sort(key=lambda c: c[0]["pageid"])  # stable order before the seeded shuffle
        page, info = seeding.shuffled(seeding.seed_for(f"{date}:music"), pool)[0]
        return self._to_track(page, info, publishable)

    @staticmethod
    def _to_track(page: dict, info: dict, publishable: set[str]) -> Track:
        original = info["url"].split("?", 1)[0]
        transcode = mp3_transcode(original)
        title = _meta(info, "ObjectName") or re.sub(
            r"\.[A-Za-z0-9]+$", "", page["title"].removeprefix("File:")).replace("_", " ")
        license_name = _meta(info, "LicenseShortName")
        return Track(
            source="Wikimedia Commons",
            license=license_name,
            public_ok=license_name in publishable,
            title=title,
            artist=_meta(info, "Artist") or "Unknown",
            audio_url=transcode or original,
            fallback_audio_url=original if transcode else "",
            ref_id=f"commons-{page['pageid']}",
            page_url=info.get("descriptionurl", ""),
            year=_meta(info, "DateTimeOriginal")[:40] or None,
            description=_meta(info, "ImageDescription")[:600],
        )
