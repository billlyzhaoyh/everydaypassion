"""Tests for the public static export and the shared render layer."""

from everydaypassion import static_site
from everydaypassion.builder import DayBuilder
from everydaypassion.config import LOCAL, public_site
from everydaypassion.library import CuratedLibrary
from everydaypassion.models import Artwork, DayPackage, Poem, Reflection
from everydaypassion.store import PackageStore
from everydaypassion.web import render


def _pkg():
    return DayPackage(
        date="2026-06-20",
        artwork=Artwork("The Met", "CC0", True, "A Title", "An Artist", "1889", "Oil", "art-1",
                        image_path="/imgs/art-1.jpg"),
        poem=Poem("PoetryDB", "Public domain", True, "A Poem", "A Poet", ["one", "two"]),
        artwork_reflection=Reflection("About the artist.", ["The Met"]),
        poem_reflection=Reflection("About the poet.", ["PoetryDB"]),
    )


def test_render_prefixes_assets_and_drops_interactivity_when_static():
    site = public_site("/everydaypassion/")
    html = render.render_day(_pkg(), site=site, date="2026-06-20", pretty="Saturday",
                             image_url="/everydaypassion/images/art-1.jpg")
    assert "/everydaypassion/static/app.css" in html
    assert "/everydaypassion/images/art-1.jpg" in html
    assert 'id="heart"' not in html       # no favorite button
    assert ">favorites<" not in html      # no favorites link
    assert "About the artist." in html and "About the poet." in html


def test_render_keeps_interactivity_for_the_local_server():
    html = render.render_day(_pkg(), site=LOCAL, date="2026-06-20", pretty="Saturday",
                             image_url="/images/art-1.jpg")
    assert "/static/app.css" in html
    assert 'id="heart"' in html
    assert "/favorites" in html


# ---- exporter fakes ------------------------------------------------------
class FakeArt:
    def __init__(self, image_path, public_ok=True):
        self.image_path = image_path
        self.public_ok = public_ok

    def fetch_artwork(self, date, seen, public_only):
        return Artwork("The Met", "CC0", self.public_ok, "Live Art", "Artist", "1889",
                       "Oil", f"art-{date}", image_path=self.image_path)


class FakePoem:
    def fetch_poem(self, date, seen, public_only):
        return Poem("PoetryDB", "Public domain", True, "Live Poem", "Poet", ["a", "b"])


class FakeWiki:
    def facts_for(self, artwork):
        return {"summary": "facts"}

    def facts_for_poet(self, poem):
        return {"summary": "facts"}


class FakeReflection:
    def write(self, artwork, facts):
        return "Artist note."

    def write_poem(self, poem, facts):
        return "Poet note."


def _builder(tmp_path, images, public_ok=True):
    return DayBuilder(
        store=PackageStore(tmp_path / "home"),
        library=CuratedLibrary(tmp_path / "curated"),
        met=FakeArt(str(images / "art-1.jpg"), public_ok=public_ok),
        poetry=FakePoem(), wiki=FakeWiki(), reflection=FakeReflection(),
        public_only=True,
    )


def test_export_writes_files_and_copies_image(tmp_path):
    images = tmp_path / "home" / "images"
    images.mkdir(parents=True)
    (images / "art-1.jpg").write_bytes(b"fake-jpeg")
    site = public_site("/everydaypassion/")
    out = tmp_path / "docs"

    warnings = static_site.write_site(
        out, _builder(tmp_path, images), images, site,
        ["2026-06-20", "2026-06-19"],
    )

    assert not warnings
    assert (out / "index.html").exists()
    assert (out / "day" / "2026-06-20.html").exists()
    assert (out / "day" / "2026-06-19.html").exists()
    assert (out / "archive.html").exists()
    assert (out / "static" / "app.css").exists()
    assert (out / "images" / "art-1.jpg").exists()
    # index is the newest day, with the base-url image link
    assert "/everydaypassion/images/art-1.jpg" in (out / "index.html").read_text()
    # archive lists both built days as static .html links
    archive = (out / "archive.html").read_text()
    assert "/everydaypassion/day/2026-06-20.html" in archive
    assert "/everydaypassion/day/2026-06-19.html" in archive


def test_export_warns_and_skips_non_public_content(tmp_path):
    images = tmp_path / "home" / "images"
    images.mkdir(parents=True)
    (images / "art-1.jpg").write_bytes(b"fake-jpeg")
    site = public_site("/everydaypassion/")
    out = tmp_path / "docs"

    warnings = static_site.write_site(
        out, _builder(tmp_path, images, public_ok=False), images, site, ["2026-06-20"],
    )

    assert any("non-public" in w for w in warnings)
    assert not (out / "day" / "2026-06-20.html").exists()
