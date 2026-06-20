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

    def facts_for_poet(self, poem):
        return {"term": poem.author, "summary": "Some poet facts."}


class FakeReflection:
    def write(self, artwork, facts):
        return f"A reflection on {artwork.title}."

    def write_poem(self, poem, facts):
        return f"A reflection on {poem.title}."


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
    assert pkg.artwork_reflection.text == "A reflection on Live Artwork."
    assert pkg.artwork_reflection.grounded_in == ["The Met", "Wikipedia"]
    assert pkg.poem_reflection.text == "A reflection on Live Poem."
    assert pkg.poem_reflection.grounded_in == ["PoetryDB", "Wikipedia"]


# ---- curator note skips the LLM ------------------------------------------
def test_quality_curator_note_is_used_verbatim_and_skips_llm(tmp_path):
    note = ("This earthenware lion was modeled by Minton & Co. in the 1850s, when the firm "
            "revived majolica glazes to dazzle the crowds at the Great Exhibition in London.")

    class CuratedMet:
        def fetch_artwork(self, date, seen, public_only):
            return Artwork("Cleveland Museum of Art", "CC0", True, "Lion", "Minton",
                           "1850", "Earthenware", "cma-1", curator_note=note)

    class BoomWiki:
        def facts_for(self, a):
            raise AssertionError("Wikipedia must be skipped when a curator note exists")

        def facts_for_poet(self, p):
            return {"summary": "poet facts"}

    class BoomReflection:
        def write(self, a, f):
            raise AssertionError("the LLM must be skipped when a curator note exists")

        def write_poem(self, p, f):
            return "poem note"

    builder, _ = _builder(tmp_path, met=CuratedMet(), poetry=FakePoetry(),
                          wiki=BoomWiki(), reflection=BoomReflection())
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork_reflection.text == note
    assert pkg.artwork_reflection.grounded_in == ["Cleveland Museum of Art"]


def test_thin_curator_note_still_uses_the_llm(tmp_path):
    class ThinNoteMet:
        def fetch_artwork(self, date, seen, public_only):
            return Artwork("The Met", "CC0", True, "Vase", "Maker", "1900", "Clay",
                           "m-1", curator_note="Too short.")

    builder, _ = _builder(tmp_path, met=ThinNoteMet(), poetry=FakePoetry(),
                          wiki=FakeWiki(), reflection=FakeReflection())
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork_reflection.text == "A reflection on Vase."


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
    pkg = builder.ensure("2026-06-19")
    assert pkg.artwork_reflection is None
    assert pkg.poem_reflection is None


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
