"""Contract tests for the network sources — fake HTTP, no live calls.

These verify request shape and parsing against recorded-style responses, so the
suite stays fast and offline-deterministic. The deterministic core logic is
covered separately in test_picker / test_store / test_builder.
"""

from everydaypassion.sources.met import MetSource
from everydaypassion.sources.poetry import PoetrySource


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
