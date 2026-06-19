"""Contract tests for the network sources — fake HTTP, no live calls.

These verify request shape and parsing against recorded-style responses, so the
suite stays fast and offline-deterministic. The deterministic core logic is
covered separately in test_picker / test_store / test_builder.
"""

import json

import pytest

from everydaypassion.models import Artwork
from everydaypassion.sources.artic import ArticSource
from everydaypassion.sources.cleveland import ClevelandSource
from everydaypassion.sources.curated import CuratedModernArt
from everydaypassion.sources.met import MetSource
from everydaypassion.sources.poetry import PoetrySource
from everydaypassion.sources.pool import SourcePool


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def get_json(self, url):
        self.requested.append(url)
        for key, payload in self.responses.items():
            if key in url:
                return payload
        raise AssertionError(f"unexpected URL: {url}")

    def download(self, url, dest):
        self.requested.append(("download", url))
        return str(dest)


def test_met_picks_a_public_domain_artwork_with_image():
    http = FakeHttp({
        "/search": {"objectIDs": [1001, 1002]},
        "/objects/1001": {"objectID": 1001, "isPublicDomain": False, "primaryImage": ""},
        "/objects/1002": {
            "objectID": 1002, "isPublicDomain": True,
            "primaryImage": "https://images.metmuseum.org/x.jpg",
            "primaryImageSmall": "https://images.metmuseum.org/x-small.jpg",
            "title": "Wheat Field", "artistDisplayName": "Van Gogh",
            "objectDate": "1889", "medium": "Oil on canvas",
        },
    })
    art = MetSource(image_dir="/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.title == "Wheat Field"
    assert art.artist == "Van Gogh"
    assert art.public_ok is True
    assert art.license == "CC0"
    assert art.ref_id == "1002"


def test_met_prefers_a_named_artist_over_unknown():
    # 1001 is public-domain with an image but has no artist; 1002 is named.
    # The picker should skip past the unnamed one to the named work.
    http = FakeHttp({
        "/search": {"objectIDs": [1001, 1002]},
        "/objects/1001": {
            "objectID": 1001, "isPublicDomain": True, "primaryImage": "u",
            "primaryImageSmall": "u", "title": "Anonymous Vase", "artistDisplayName": "",
        },
        "/objects/1002": {
            "objectID": 1002, "isPublicDomain": True, "primaryImage": "u",
            "primaryImageSmall": "u", "title": "Portrait", "artistDisplayName": "A Painter",
        },
    })
    art = MetSource(image_dir="/tmp/edp-test", http=http, max_probe=10).fetch_artwork("2026-06-19")
    assert art.artist == "A Painter"


def test_met_falls_back_to_unnamed_when_no_named_artist():
    http = FakeHttp({
        "/search": {"objectIDs": [1001]},
        "/objects/1001": {
            "objectID": 1001, "isPublicDomain": True, "primaryImage": "u",
            "primaryImageSmall": "u", "title": "Anonymous Vase", "artistDisplayName": "",
        },
    })
    art = MetSource(image_dir="/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.title == "Anonymous Vase"
    assert art.artist == "Unknown"


def test_met_is_deterministic_for_a_date():
    payload = {
        "/search": {"objectIDs": [1, 2, 3, 4, 5]},
    }
    for oid in range(1, 6):
        payload[f"/objects/{oid}"] = {
            "objectID": oid, "isPublicDomain": True,
            "primaryImage": "u", "primaryImageSmall": "u",
            "title": f"Art {oid}", "artistDisplayName": "Artist",
        }
    a = MetSource(image_dir="/tmp/edp-test", http=FakeHttp(dict(payload))).fetch_artwork("2026-06-19")
    b = MetSource(image_dir="/tmp/edp-test", http=FakeHttp(dict(payload))).fetch_artwork("2026-06-19")
    assert a.ref_id == b.ref_id


def test_poetry_filters_by_length_and_parses():
    http = FakeHttp({
        "/author/": [
            {"title": "Epic", "author": "A Poet", "lines": ["l"] * 80, "linecount": "80"},
            {"title": "Short Gem", "author": "A Poet", "lines": ["one", "two"], "linecount": "2"},
        ],
    })
    poem = PoetrySource(http=http, authors=["A Poet"], max_lines=30).fetch_poem("2026-06-19")
    assert poem.title == "Short Gem"
    assert poem.public_ok is True
    assert poem.lines == ["one", "two"]


def test_poetry_taste_gate_rejects_and_redraws():
    http = FakeHttp({
        "/author/": [
            {"title": "Doggerel", "author": "A Poet", "lines": ["bad"]},
            {"title": "Worthy", "author": "A Poet", "lines": ["good"]},
        ],
    })
    gate = lambda lines: lines != ["bad"]
    poem = PoetrySource(http=http, authors=["A Poet"], taste_gate=gate).fetch_poem("2026-06-19")
    assert poem.title == "Worthy"


# ---- new museum sources, pool, and curated modern art -------------------
def test_artic_prefers_named_public_domain_work():
    http = FakeHttp({
        "api.artic.edu": {
            "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
            "data": [
                {"id": 1, "title": "Anonymous Bowl", "artist_title": None, "image_id": "a"},
                {"id": 2, "title": "The Bedroom", "artist_title": "Vincent van Gogh",
                 "date_display": "1889", "medium_display": "Oil", "image_id": "b"},
            ],
        },
    })
    art = ArticSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.artist == "Vincent van Gogh"
    assert art.ref_id == "artic-2"
    assert art.source == "Art Institute of Chicago"


def test_cleveland_extracts_artist_name_and_image():
    http = FakeHttp({
        "clevelandart.org": {
            "data": [
                {"id": 9, "title": "Stag at Sharkey's",
                 "creators": [{"description": "George Bellows (American, 1882–1925)"}],
                 "creation_date": "1909", "technique": "Oil on canvas",
                 "images": {"web": {"url": "https://x/img.jpg"}}},
            ],
        },
    })
    art = ClevelandSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.artist == "George Bellows"
    assert art.ref_id == "cma-9"
    assert art.license == "CC0"


def test_source_pool_rotates_and_falls_through():
    class Down:
        def fetch_artwork(self, date, seen, public_only):
            raise RuntimeError("source down")

    class Up:
        def fetch_artwork(self, date, seen, public_only):
            return Artwork("Up", "CC0", True, "Title", "Artist", "", "", "up-1")

    pool = SourcePool([Down(), Up()], "art")
    art = pool.fetch_artwork("2026-06-19", set(), False)
    assert art.title == "Title"


def test_curated_modern_art_empty_falls_through(tmp_path):
    src = CuratedModernArt(tmp_path, tmp_path)  # no artworks_modern.json
    with pytest.raises(LookupError):
        src.fetch_artwork("2026-06-19")


def test_curated_modern_art_picks_and_resolves_image(tmp_path):
    (tmp_path / "artworks_modern.json").write_text(json.dumps([
        {"source": "curated", "license": "© the artist", "public_ok": False,
         "title": "Angelus Novus", "artist": "Paul Klee", "date": "1920",
         "medium": "Oil transfer", "ref_id": "klee-angelus", "image_path": "klee.jpg"},
    ]))
    images = tmp_path / "images"
    images.mkdir()
    art = CuratedModernArt(tmp_path, images).fetch_artwork("2026-06-19")
    assert art.artist == "Paul Klee"
    assert art.image_path == str(images / "klee.jpg")
    # a public build excludes the copyrighted modern piece
    with pytest.raises(LookupError):
        CuratedModernArt(tmp_path, images).fetch_artwork("2026-06-19", public_only=True)
