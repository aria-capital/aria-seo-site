"""
Tests for build_curated_sitemap.py.

The sitemap decides what Google is invited to crawl. Advertising all 1,461 AI-generated
articles at once is the manual-action risk the plan of record warns about, so the selection
rule is the load-bearing part — and it must never quietly drop to advertising everything.
"""
import re

import pytest

import build_curated_sitemap as bcs


def _page(words, chrome=True):
    body = " ".join(["word"] * words)
    extra = "<script>var x=1;</script><nav>Home About</nav><footer>c 2026</footer>" if chrome else ""
    return f"<html><head></head><body>{extra}<p>{body}</p></body></html>"


# --- body_words -------------------------------------------------------------


def test_body_words_counts_prose():
    assert bcs.body_words(_page(50, chrome=False)) == 50


def test_body_words_ignores_script_style_nav_footer_form():
    """Chrome is identical on every page; counting it would make thin pages look substantial."""
    assert bcs.body_words(_page(50)) == 50


def test_body_words_ignores_markup():
    assert bcs.body_words("<div><p><strong>one</strong> two</p></div>") == 2


# --- selection --------------------------------------------------------------


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(bcs, "HERE", str(tmp_path))
    return tmp_path


def _write(site, name, words):
    (site / name).write_text(_page(words), encoding="utf-8")


def test_thin_articles_are_excluded(site):
    _write(site, "thin.html", 100)
    _write(site, "good.html", 1200)
    chosen, stats = bcs.select(target=10, min_words=600)
    assert chosen == ["good.html"]
    assert stats["thin_excluded"] == 1


def test_meta_pages_are_never_selected(site):
    _write(site, "about.html", 2000)
    _write(site, "index.html", 2000)
    _write(site, "real-article.html", 1200)
    chosen, _ = bcs.select(target=10, min_words=600)
    assert chosen == ["real-article.html"]


def test_selection_takes_the_longest_first(site):
    for name, words in (("a.html", 700), ("b.html", 2000), ("c.html", 1200)):
        _write(site, name, words)
    chosen, _ = bcs.select(target=2, min_words=600)
    assert set(chosen) == {"b.html", "c.html"}, "the two longest, not the first two by name"


def test_target_caps_the_batch(site):
    for i in range(20):
        _write(site, f"a{i:02d}.html", 1000 + i)
    chosen, stats = bcs.select(target=5, min_words=600)
    assert len(chosen) == 5
    assert stats["held_back"] == 15


def test_output_is_sorted_for_a_stable_diff(site):
    for name in ("c.html", "a.html", "b.html"):
        _write(site, name, 1000)
    chosen, _ = bcs.select(target=10, min_words=600)
    assert chosen == sorted(chosen)


# --- xml --------------------------------------------------------------------


def test_xml_is_wellformed_and_includes_core_pages():
    import xml.dom.minidom as minidom

    xml = bcs.build_xml(["guide.html"], "https://x.test/s/")
    minidom.parseString(xml)
    assert "<loc>https://x.test/s/</loc>" in xml
    assert "<loc>https://x.test/s/guide.html</loc>" in xml
    assert "<loc>https://x.test/s/about.html</loc>" in xml


def test_every_loc_is_absolute_on_the_given_host():
    xml = bcs.build_xml(["a.html", "b.html"], "https://x.test/s/")
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        assert loc.startswith("https://x.test/s/")


# --- the live sitemap -------------------------------------------------------


def test_live_sitemap_is_curated_not_the_whole_corpus():
    """
    The invariant this script exists to hold. If a future change points the sitemap back at
    every article, the site returns to matching Google's scaled-content pattern.
    """
    import os

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "sitemap.xml"), encoding="utf-8") as fh:
        locs = re.findall(r"<loc>([^<]+)</loc>", fh.read())
    articles = len([f for f in os.listdir(here) if f.endswith(".html")])

    assert len(locs) < articles, "sitemap advertises the entire corpus"
    assert len(locs) > 100, "sitemap is suspiciously small"


def test_live_sitemap_locs_all_resolve():
    """A sitemap entry pointing at a missing file is a crawl error on every fetch."""
    import os

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "sitemap.xml"), encoding="utf-8") as fh:
        locs = re.findall(r"<loc>([^<]+)</loc>", fh.read())
    for loc in locs:
        slug = loc.rstrip("/").split("/")[-1]
        if slug.endswith(".html"):
            assert os.path.exists(os.path.join(here, slug)), slug
