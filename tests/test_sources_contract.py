"""Contract tests for the network sources — fake HTTP, no live calls.

These verify request shape and parsing against recorded-style responses, so the
suite stays fast and offline-deterministic. The deterministic core logic is
covered separately in test_seeding / test_store / test_builder.
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
from everydaypassion.sources.rijks import RijksSource
from everydaypassion.sources.smk import SmkSource
from everydaypassion.sources.vam import VamSource


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
    # only the returned work's image is downloaded, never the skipped candidate's
    assert [r for r in http.requested if isinstance(r, tuple)] == [("download", "u")]


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


def test_poetry_one_poets_outage_moves_on_to_the_next():
    class FlakyHttp(FakeHttp):
        def get_json(self, url):
            if "Down" in url:
                raise TimeoutError("PoetryDB timed out")
            return super().get_json(url)

    http = FlakyHttp({"/author/Up": [{"title": "Survivor", "author": "Up", "lines": ["x"]}]})
    for day in range(1, 8):  # whichever order the poets come in, the day survives
        poem = PoetrySource(http=http, authors=["Down", "Up"]).fetch_poem(f"2026-06-{day:02d}")
        assert poem.title == "Survivor"


def test_poetry_taste_gate_calls_are_capped_and_cached():
    http = FakeHttp({"/author/": [
        {"title": f"P{i}", "author": "A Poet", "lines": [str(i)]} for i in range(10)]})
    calls = []
    gate = lambda lines: calls.append(lines) or False  # rejects everything
    src = PoetrySource(http=http, authors=["A Poet"], taste_gate=gate, max_gate_calls=3)
    first = src.fetch_poem("2026-06-19")
    assert len(calls) == 3  # budget spent, then the next candidate is accepted
    again = src.fetch_poem("2026-06-19")  # e.g. the builder's retry
    assert len(calls) == 3  # cached verdicts: no new model calls
    assert again.title == first.title


# ---- new museum sources, pool, and curated modern art -------------------
def test_artic_prefers_named_public_domain_work():
    http = FakeHttp({
        "api.artic.edu": {
            "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
            "data": [
                {"id": 1, "title": "Anonymous Bowl", "artist_title": None, "image_id": "a"},
                {"id": 2, "title": "The Bedroom", "artist_title": "Vincent van Gogh",
                 "date_display": "1889", "medium_display": "Oil", "image_id": "b",
                 "short_description": "One of three versions of his Arles bedroom.",
                 "description": "<p>Perhaps the most <em>famous</em> bedroom in art.</p>"},
            ],
        },
    })
    art = ArticSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.artist == "Vincent van Gogh"
    assert art.ref_id == "artic-2"
    assert art.source == "Art Institute of Chicago"
    # curator text is captured for grounding, with markup stripped
    assert art.details["Curator's summary"] == "One of three versions of his Arles bedroom."
    assert art.details["Curatorial description"] == "Perhaps the most famous bedroom in art."
    # the description becomes the displayable curator note (markup stripped),
    # credited under its own licence (CC BY 4.0, unlike the CC0 image)
    assert art.curator_note == "Perhaps the most famous bedroom in art."
    assert art.curator_note_license == "CC BY 4.0"
    assert art.license == "CC0"


def test_artic_stays_within_the_paging_window():
    http = FakeHttp({"api.artic.edu": {"data": [
        {"id": 2, "title": "T", "artist_title": "A", "image_id": "b"}]}})
    for day in range(1, 29):
        ArticSource("/tmp/edp-test", http=http).fetch_artwork(f"2026-02-{day:02d}")
    pages = [int(u.split("page=")[1]) for u in http.requested
             if isinstance(u, str) and "page=" in u]
    assert pages and max(pages) <= 10


def test_cleveland_extracts_artist_name_and_image():
    http = FakeHttp({
        "clevelandart.org": {
            "data": [
                {"id": 9, "title": "Stag at Sharkey's",
                 "creators": [{"description": "George Bellows (American, 1882–1925)"}],
                 "creation_date": "1909", "technique": "Oil on canvas",
                 "description": "Bellows depicts a brutal boxing match.",
                 "did_you_know": "Sharkey's was a saloon near the artist's studio.",
                 "images": {"web": {"url": "https://x/img.jpg"}}},
            ],
        },
    })
    art = ClevelandSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.artist == "George Bellows"
    assert art.ref_id == "cma-9"
    assert art.license == "CC0"
    assert art.details["Curatorial description"] == "Bellows depicts a brutal boxing match."
    assert art.details["Did you know"] == "Sharkey's was a saloon near the artist's studio."
    # description + did-you-know compose the displayable curator note
    assert art.curator_note == (
        "Bellows depicts a brutal boxing match.\n\n"
        "Did you know? Sharkey's was a saloon near the artist's studio."
    )


def test_cleveland_skips_records_not_marked_cc0():
    http = FakeHttp({
        "clevelandart.org": {
            "data": [
                {"id": 1, "title": "Copyrighted", "share_license_status": "Copyrighted",
                 "creators": [{"description": "Someone (American)"}]},
                {"id": 2, "title": "Open", "share_license_status": "CC0",
                 "creators": [{"description": "Another (American)"}]},
            ],
        },
    })
    art = ClevelandSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.title == "Open"


def test_smk_parses_cc0_record_with_image():
    http = FakeHttp({
        "api.smk.dk": {
            "items": [
                {"object_number": "KKS1", "titles": [{"title": "Overraskelsen"}],
                 "artist": ["Ugo da Carpi"], "production_date": [{"period": "1510-1520"}],
                 "techniques": ["Træsnit"],
                 "image_thumbnail": "https://iip-thumb.smk.dk/x/full/!1024,/0/default.jpg"},
            ],
        },
    })
    art = SmkSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.title == "Overraskelsen"
    assert art.artist == "Ugo da Carpi"
    assert art.ref_id == "smk-KKS1"
    assert art.license == "Public Domain Mark 1.0"
    assert art.public_ok is True


def test_vam_builds_iiif_image_and_is_personal_use():
    http = FakeHttp({
        "api.vam.ac.uk": {
            "records": [
                {"systemNumber": "O429002", "_primaryTitle": "Krishna painting Radha",
                 "_primaryMaker": {"name": "George Keyt"}, "_primaryDate": "1932",
                 "objectType": "Painting",
                 "_images": {"_iiif_image_base_url": "https://framemark.vam.ac.uk/collections/2006AM2326/"}},
            ],
        },
    })
    art = VamSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19")
    assert art.artist == "George Keyt"
    assert art.ref_id == "va-O429002"
    assert art.public_ok is False
    # cache_image fell back to the constructed IIIF URL (FakeHttp.download echoes dest,
    # so just assert the source asked for an image at all)
    assert art.image_path is not None


def test_vam_skips_itself_in_a_public_build():
    # No HTTP call should happen — it bails before fetching.
    src = VamSource("/tmp/edp-test", http=FakeHttp({}))
    with pytest.raises(Exception):
        src.fetch_artwork("2026-06-19", public_only=True)


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


def test_taste_gate_uses_the_small_model_and_tolerates_markdown():
    from types import SimpleNamespace

    from everydaypassion.sources.reflection import ReflectionWriter

    sent = {}

    class FakeMessages:
        def __init__(self, reply):
            self.reply = reply

        def create(self, **kw):
            sent.update(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])

    def writer(reply):
        return ReflectionWriter(client=SimpleNamespace(messages=FakeMessages(reply)),
                                gate_model="small-model")

    assert writer("**YES**").taste_ok(["a line"]) is True
    assert sent["model"] == "small-model"
    assert sent["thinking"] == {"type": "disabled"}
    assert writer("Yes.").taste_ok(["a line"]) is True
    assert writer("NO").taste_ok(["a line"]) is False


def _rijks_object(rights, creator, title):
    en = [{"id": "http://vocab.getty.edu/aat/300388277"}]
    return {
        "identified_by": [{"type": "Name", "content": title, "language": en}],
        "produced_by": {
            "timespan": {"identified_by": [{"content": "1626", "language": en}]},
            "referred_to_by": [{"content": creator, "language": en,
                                "classified_as": [{"id": "http://vocab.getty.edu/aat/300435416"}]}],
            "part": [{"carried_out_by": [{"notation": [{"@language": "en", "@value": creator}],
                                          "equivalent": [{"id": "http://www.wikidata.org/entity/Q5598"}]}]}],
        },
        "referred_to_by": [{"content": "oil on panel", "language": en,
                            "classified_as": [{"id": "http://vocab.getty.edu/aat/300435429"}]}],
        "subject_of": [{"digitally_carried_by": [{
            "access_point": [{"id": "https://iiif.micr.io/abc/full/max/0/default.jpg"}],
            "referred_to_by": [{"content": rights}]}]}],
    }


def test_rijks_takes_only_free_images_and_parses_linked_art():
    http = FakeHttp({
        "search/collection": {"orderedItems": [{"id": "https://id.rijksmuseum.nl/1"},
                                               {"id": "https://id.rijksmuseum.nl/2"}]},
        "data.rijksmuseum.nl/1": _rijks_object(
            "https://rightsstatements.org/vocab/InC/1.0/", "Karel Appel", "In copyright"),
        "data.rijksmuseum.nl/2": _rijks_object(
            "https://creativecommons.org/publicdomain/mark/1.0/", "Rembrandt van Rijn",
            "Tobit and Anna with the Kid"),
    })
    art = RijksSource("/tmp/edp-test", http=http).fetch_artwork("2026-06-19", public_only=True)
    assert art.title == "Tobit and Anna with the Kid"
    assert art.artist == "Rembrandt van Rijn"
    assert art.license == "Public Domain Mark 1.0" and art.public_ok is True
    assert art.medium == "oil on panel" and art.date == "1626"
    assert art.ref_id == "rijks-2"
    assert art.image_url == "https://iiif.micr.io/abc/full/843,/0/default.jpg"
    assert art.artist_url == "http://www.wikidata.org/entity/Q5598"


# ---- Standard Ebooks (poetry + prose) -----------------------------------
_OPF = ('<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<metadata><dc:creator id="author">{author}</dc:creator></metadata></package>')
_X = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
      '<body>{body}</body></html>')


class FakeTextHttp:
    def __init__(self, pages):
        self.pages = pages

    def get_text(self, url):
        for key, text in self.pages.items():
            if url.endswith(key):
                return text
        raise AssertionError(f"unexpected URL: {url}")


def _poem(pid, n):
    lines = "<br/>".join(f"<span>line {i}</span>" for i in range(n))
    return f'<article id="{pid}" epub:type="z3998:poem"><h2>{pid}</h2><p>{lines}</p></article>'


def test_standard_ebooks_poetry_extracts_a_short_poem():
    from everydaypassion.sources.standardebooks import LICENSE, StandardEbooksPoetry

    toc = _X.format(body='<nav><a href="text/titlepage.xhtml">Titlepage</a>'
                         '<a href="text/poetry.xhtml#epic">Epic</a>'
                         '<a href="text/poetry.xhtml#gem">Dust of Snow</a></nav>')
    http = FakeTextHttp({
        "content.opf": _OPF.format(author="Robert Frost"),
        "toc.xhtml": toc,
        "text/poetry.xhtml": _X.format(body=_poem("epic", 80) + _poem("gem", 8)),
    })
    poem = StandardEbooksPoetry(http=http, collections=["robert-frost_new-hampshire"]) \
        .fetch_poem("2026-06-19")
    assert poem.title == "Dust of Snow" and poem.author == "Robert Frost"
    assert poem.lines == [f"line {i}" for i in range(8)]
    assert poem.license == LICENSE and poem.public_ok is True


def test_standard_ebooks_prose_keeps_a_story_of_reading_length():
    from everydaypassion.sources.standardebooks import StandardEbooksProse

    para = "<p>" + " ".join(["word"] * 100) + "</p>"
    toc = _X.format(body='<nav><a href="text/long.xhtml">Long</a>'
                         '<a href="text/hands.xhtml">Hands</a>'
                         '<a href="text/hands.xhtml#hands-1">I</a></nav>')
    http = FakeTextHttp({
        "content.opf": _OPF.format(author="Sherwood Anderson"),
        "toc.xhtml": toc,
        "text/long.xhtml": _X.format(body=f'<article epub:type="se:short-story">{para * 60}</article>'),
        "text/hands.xhtml": _X.format(body='<article epub:type="se:short-story"><h2>Hands</h2>'
                                            f'<section id="hands-1">{para * 12}</section></article>'),
    })
    prose = StandardEbooksProse(http=http, collections=["sherwood-anderson_winesburg-ohio"]) \
        .fetch_prose("2026-06-19")
    assert prose.title == "Hands" and prose.kind == "story"
    assert prose.word_count == 1200 and len(prose.paragraphs) == 12
    assert prose.minutes == 5
    assert prose.source_url == "https://github.com/standardebooks/sherwood-anderson_winesburg-ohio"
