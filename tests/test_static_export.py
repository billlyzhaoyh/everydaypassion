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
    def __init__(self, image_path, public_ok=True, title="Live Art"):
        self.image_path = image_path
        self.public_ok = public_ok
        self.title = title
        self.seen_args = []

    def fetch_artwork(self, date, seen, public_only):
        self.seen_args.append(set(seen))
        return Artwork("The Met", "CC0", self.public_ok, self.title, "Artist", "1889",
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


def _builder(tmp_path, images, public_ok=True, art=None):
    return DayBuilder(
        store=PackageStore(tmp_path / "home"),
        library=CuratedLibrary(tmp_path / "curated"),
        met=art or FakeArt(str(images / "art-1.jpg"), public_ok=public_ok),
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
        ["2026-06-20", "2026-06-19"], data_dir=tmp_path / "data",
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
        data_dir=tmp_path / "data",
    )

    assert any("non-public" in w for w in warnings)
    assert not (out / "day" / "2026-06-20.html").exists()


def test_export_freezes_published_days_and_keeps_its_own_seen_log(tmp_path):
    images = tmp_path / "home" / "images"
    images.mkdir(parents=True)
    (images / "art-1.jpg").write_bytes(b"fake-jpeg")
    site, out, data = public_site("/everydaypassion/"), tmp_path / "site", tmp_path / "data"

    static_site.write_site(out, _builder(tmp_path, images), images, site,
                           ["2026-06-19"], data_dir=data)
    assert (data / "packages" / "2026-06-19.json").exists()
    assert "art-2026-06-19" in PackageStore(data).seen_ids()

    # A fresh runner: new output dir, same committed data. The published day is
    # re-rendered from data (not rebuilt), and the next day sees the seen log.
    art = FakeArt(str(images / "art-1.jpg"), title="Different Art")
    static_site.write_site(tmp_path / "site2", _builder(tmp_path, images, art=art), images,
                           site, ["2026-06-20", "2026-06-19"], data_dir=data)
    assert "Live Art" in (tmp_path / "site2" / "day" / "2026-06-19.html").read_text()
    assert len(art.seen_args) == 1  # only 2026-06-20 was built
    assert "art-2026-06-19" in art.seen_args[0]

    # --rebuild regenerates a published day on purpose
    static_site.write_site(tmp_path / "site3", _builder(tmp_path, images, art=art), images,
                           site, ["2026-06-19"], data_dir=data, rebuild=True)
    assert "Different Art" in (tmp_path / "site3" / "day" / "2026-06-19.html").read_text()


def test_export_keeps_legacy_pages_and_indexes_the_newest_day(tmp_path):
    images = tmp_path / "home" / "images"
    images.mkdir(parents=True)
    (images / "art-1.jpg").write_bytes(b"fake-jpeg")
    out = tmp_path / "site"
    (out / "day").mkdir(parents=True)
    (out / "day" / "2026-06-18.html").write_text("legacy page")

    static_site.write_site(out, _builder(tmp_path, images), images,
                           public_site("/everydaypassion/"),
                           ["2026-06-19", "2026-06-18"], data_dir=tmp_path / "data")
    assert (out / "day" / "2026-06-18.html").read_text() == "legacy page"
    assert (out / "index.html").read_text() == (out / "day" / "2026-06-19.html").read_text()
    assert "/everydaypassion/day/2026-06-18.html" in (out / "archive.html").read_text()


def test_export_refetches_an_image_missing_from_the_cache(tmp_path):
    images = tmp_path / "cache"
    images.mkdir()
    art = Artwork("The Met", "CC0", True, "T", "A", "", "", "1",
                  image_path="/home/runner/.everydaypassion/images/met-1.jpg",
                  image_url="https://images.example/met-1.jpg")
    fetched = []

    def download(url, dest):
        fetched.append(url)
        dest.write_bytes(b"jpeg")

    dest = tmp_path / "out"
    dest.mkdir()
    url = static_site._export_image(art, images, dest, public_site("/edp/"), download=download)
    assert fetched == ["https://images.example/met-1.jpg"]
    assert url == "/edp/images/met-1.jpg"
    assert (dest / "met-1.jpg").exists()


def test_render_shows_the_story_collapsed_with_reading_time():
    from everydaypassion.models import Prose

    pkg = _pkg()
    pkg.story = Prose("Standard Ebooks", "Public domain", True, "Hands", "Sherwood Anderson",
                      paragraphs=["Upon the half-decayed veranda.", "Second paragraph."],
                      word_count=2300, source_url="https://github.com/standardebooks/x")
    pkg.story_reflection = Reflection("About Anderson.", ["Standard Ebooks"])
    html = render.render_day(pkg, site=LOCAL, date="2026-06-20", pretty="Saturday",
                             image_url=None)
    assert "Today's story" in html and "about 10 min" in html
    assert "<p>Upon the half-decayed veranda.</p>" in html
    assert "About Anderson." in html


def test_render_streams_music_without_preloading():
    from everydaypassion.models import Track

    pkg = _pkg()
    pkg.music = Track("Wikimedia Commons", "CC0", True, "Aria", "Kimiko Ishizaka",
                      "https://upload.wikimedia.org/t/a.ogg.mp3", "commons-1",
                      fallback_audio_url="https://upload.wikimedia.org/a.ogg",
                      page_url="https://commons.wikimedia.org/wiki/File:a.ogg")
    html = render.render_day(pkg, site=public_site("/edp/"), date="2026-06-20",
                             pretty="Saturday", image_url=None)
    assert '<audio controls preload="none">' in html
    assert html.index("a.ogg.mp3") < html.index('src="https://upload.wikimedia.org/a.ogg"')
    assert "Today's music" in html
