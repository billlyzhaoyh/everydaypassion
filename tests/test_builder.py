import json

from everydaypassion.builder import DayBuilder
from everydaypassion.library import CuratedLibrary
from everydaypassion.models import Artwork, Poem
from everydaypassion.store import PackageStore


# ---- fakes ---------------------------------------------------------------
class FakeMet:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def fetch_artwork(self, date, seen, public_only):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Met is down")
        return Artwork("The Met", "CC0", True, "Live Artwork", "Artist", "1889", "Oil", "live-art")


class FakePoetry:
    def __init__(self, fail=False):
        self.fail = fail

    def fetch_poem(self, date, seen, public_only):
        if self.fail:
            raise RuntimeError("PoetryDB is down")
        return Poem("PoetryDB", "Public domain", True, "Live Poem", "Poet", ["line"])


class FakeWiki:
    def facts_for(self, artwork):
        return {"term": artwork.artist, "summary": "Some real facts."}


class FakeReflection:
    def write(self, artwork, facts):
        return f"A reflection on {artwork.title}."


def _library(tmp_path):
    poems = [{"source": "curated", "license": "Public domain", "public_ok": True,
              "title": "Fallback Poem", "author": "PD Poet", "lines": ["x"]}]
    arts = [{"source": "curated", "license": "CC0", "public_ok": True, "title": "Fallback Artwork",
             "artist": "PD Artist", "date": "1800", "medium": "Oil", "ref_id": "fallback-art"}]
    (tmp_path / "poems.json").write_text(json.dumps(poems))
    (tmp_path / "artworks.json").write_text(json.dumps(arts))
    return CuratedLibrary(tmp_path)


def _builder(tmp_path, **kw):
    store = PackageStore(tmp_path / "state")
    library = _library(tmp_path)
    return DayBuilder(store=store, library=library, **kw), store


# ---- happy path ----------------------------------------------------------
def test_happy_path_assembles_from_live_sources(tmp_path):
    builder, _ = _builder(tmp_path, met=FakeMet(), poetry=FakePoetry(),
                          wiki=FakeWiki(), reflection=FakeReflection())
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork.title == "Live Artwork"
    assert pkg.poem.title == "Live Poem"
    assert pkg.reflection.text == "A reflection on Live Artwork."
    assert pkg.reflection.grounded_in == ["The Met", "Wikipedia"]


# ---- fallback policy -----------------------------------------------------
def test_artwork_falls_back_to_library_when_met_fails(tmp_path):
    builder, _ = _builder(tmp_path, met=FakeMet(fail=True), poetry=FakePoetry())
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork.title == "Fallback Artwork"
    assert pkg.poem.title == "Live Poem"  # poem source still healthy


def test_poem_falls_back_to_library_when_poetry_fails(tmp_path):
    builder, _ = _builder(tmp_path, met=FakeMet(), poetry=FakePoetry(fail=True))
    pkg = builder.ensure("2026-06-19")
    assert pkg.poem.title == "Fallback Poem"


def test_reflection_is_optional_when_no_writer(tmp_path):
    builder, _ = _builder(tmp_path, met=FakeMet(), poetry=FakePoetry())
    assert builder.ensure("2026-06-19").reflection is None


def test_fully_offline_still_builds_a_morning(tmp_path):
    builder, _ = _builder(tmp_path)  # no live sources at all
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork.title == "Fallback Artwork"
    assert pkg.poem.title == "Fallback Poem"


# ---- freeze + seen -------------------------------------------------------
def test_ensure_is_idempotent_and_frozen(tmp_path):
    met = FakeMet()
    builder, store = _builder(tmp_path, met=met, poetry=FakePoetry())
    builder.ensure("2026-06-19")
    calls_after_first = met.calls
    builder.ensure("2026-06-19")  # second call must read, not rebuild
    assert met.calls == calls_after_first


def test_built_items_are_marked_seen(tmp_path):
    builder, store = _builder(tmp_path, met=FakeMet(), poetry=FakePoetry())
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork.ref_id in store.seen_ids()
    assert pkg.poem.ref_id in store.seen_ids()


def test_retry_recovers_within_budget(tmp_path):
    class FlakyMet:
        def __init__(self):
            self.calls = 0

        def fetch_artwork(self, date, seen, public_only):
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("transient blip")
            return Artwork("The Met", "CC0", True, "Recovered", "Artist", "1889", "Oil", "rec")

    builder, _ = _builder(tmp_path, met=FlakyMet(), poetry=FakePoetry(), retries=2)
    assert builder.ensure("2026-06-19").artwork.title == "Recovered"
