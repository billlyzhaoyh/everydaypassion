from everydaypassion.models import Artwork, DayPackage, Poem, Reflection
from everydaypassion.store import PackageStore


def _pkg(date="2026-06-19", title="Wheat Field"):
    return DayPackage(
        date=date,
        artwork=Artwork("The Met", "CC0", True, title, "Van Gogh", "1889", "Oil", "ref-1"),
        poem=Poem("PoetryDB", "Public domain", True, "Dust of Snow", "Frost", ["a", "b"]),
        reflection=Reflection("A grounded note.", ["The Met", "Wikipedia"]),
    )


def test_write_then_read_roundtrips(tmp_path):
    store = PackageStore(tmp_path)
    store.write(_pkg())
    got = store.read("2026-06-19")
    assert got.artwork.title == "Wheat Field"
    assert got.poem.author == "Frost"
    assert got.reflection.text == "A grounded note."


def test_a_built_date_is_frozen(tmp_path):
    store = PackageStore(tmp_path)
    assert store.write(_pkg(title="Original")) is True
    assert store.write(_pkg(title="Changed")) is False  # freeze rule refuses
    assert store.read("2026-06-19").artwork.title == "Original"


def test_overwrite_is_possible_only_when_explicit(tmp_path):
    store = PackageStore(tmp_path)
    store.write(_pkg(title="Original"))
    assert store.write(_pkg(title="Changed"), overwrite=True) is True
    assert store.read("2026-06-19").artwork.title == "Changed"


def test_seen_ids_accumulate(tmp_path):
    store = PackageStore(tmp_path)
    store.mark_seen("ref-1", "ref-2")
    store.mark_seen("ref-2", "ref-3", "")
    assert store.seen_ids() == {"ref-1", "ref-2", "ref-3"}


def test_favorites_add_toggle_and_list(tmp_path):
    store = PackageStore(tmp_path)
    assert store.toggle_favorite("2026-06-19") is True
    assert store.is_favorite("2026-06-19")
    assert store.toggle_favorite("2026-06-19") is False
    assert store.favorites() == []


def test_archive_is_sorted_newest_first(tmp_path):
    store = PackageStore(tmp_path)
    for d in ("2026-06-18", "2026-06-20", "2026-06-19"):
        store.write(_pkg(date=d))
    assert store.archive() == ["2026-06-20", "2026-06-19", "2026-06-18"]
