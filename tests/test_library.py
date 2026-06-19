import json

from everydaypassion.library import CuratedLibrary


def _seed(tmp_path):
    poems = [
        {"source": "PoetryDB", "license": "Public domain", "public_ok": True,
         "title": "Dust of Snow", "author": "Frost", "lines": ["a", "b"]},
        {"source": "curated", "license": "© poet", "public_ok": False,
         "title": "A Modern Poem", "author": "Living Poet", "lines": ["c"]},
    ]
    arts = [
        {"source": "The Met", "license": "CC0", "public_ok": True, "title": "Wheat Field",
         "artist": "Van Gogh", "date": "1889", "medium": "Oil", "ref_id": "met-1"},
    ]
    (tmp_path / "poems.json").write_text(json.dumps(poems))
    (tmp_path / "artworks.json").write_text(json.dumps(arts))
    return CuratedLibrary(tmp_path)


def test_loads_poems_and_artworks(tmp_path):
    lib = _seed(tmp_path)
    assert len(lib.poems()) == 2
    assert len(lib.artworks()) == 1


def test_public_only_filters_copyrighted_items(tmp_path):
    lib = _seed(tmp_path)
    public = lib.poems(public_only=True)
    assert len(public) == 1
    assert all(p.public_ok for p in public)


def test_get_is_deterministic(tmp_path):
    lib = _seed(tmp_path)
    assert lib.get_poem("2026-06-19:poem").title == lib.get_poem("2026-06-19:poem").title


def test_missing_files_yield_empty(tmp_path):
    lib = CuratedLibrary(tmp_path)
    assert lib.poems() == []
    assert lib.artworks() == []
