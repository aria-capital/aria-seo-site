"""
Tests for apply_noindex_to_uncurated.py.

This mutator touches 518 live articles, so the properties that matter are the ones that
stop a second run doing damage: idempotency, exact reversibility, and never de-indexing
something the sitemap advertises.

The selection rule is deliberately derived from sitemap.xml rather than from a list, so
the two can never drift apart. A test pins that, because a drifted copy would silently
de-index advertised pages — the exact opposite of the intent.
"""
import os
import sys
import re

import pytest

import apply_noindex_to_uncurated as noindex

HEAD = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<title>T</title>\n</head>\n"
BODY = "<body><div>content</div></body>\n</html>\n"
PAGE = HEAD + BODY


# --- the tag ----------------------------------------------------------------


def test_tag_is_added_inside_head():
    out = noindex.add_noindex(PAGE)
    assert noindex.TAG in out
    assert out.index(noindex.TAG) < out.index("</head>"), "tag must be inside <head>"


def test_tag_says_noindex_follow():
    """
    `follow` is load-bearing, not decoration: these pages are linked from 10-43 curated
    pages each. noindex,nofollow would strand internal link equity.
    """
    assert "noindex" in noindex.TAG and "follow" in noindex.TAG
    assert "nofollow" not in noindex.TAG


def test_adding_is_idempotent():
    """These scripts get re-run casually. A second run must change nothing."""
    once = noindex.add_noindex(PAGE)
    assert noindex.add_noindex(once) == once


def test_repeated_runs_never_stack_tags():
    out = PAGE
    for _ in range(5):
        out = noindex.add_noindex(out)
    assert len(re.findall(r'name="robots"', out)) == 1


def test_an_existing_contradictory_robots_tag_is_replaced_not_duplicated():
    """A page saying 'index, follow' must end up saying noindex, not both."""
    page = PAGE.replace("<title>T</title>", '<meta name="robots" content="index, follow" />\n<title>T</title>')
    out = noindex.add_noindex(page)
    assert len(re.findall(r'name="robots"', out)) == 1
    assert "noindex" in out
    assert 'content="index, follow"' not in out


def test_removal_is_an_exact_reversal():
    """The escape hatch has to actually work, byte for byte."""
    assert noindex.remove_noindex(noindex.add_noindex(PAGE)) == PAGE


def test_removal_is_idempotent():
    once = noindex.remove_noindex(PAGE)
    assert noindex.remove_noindex(once) == once


def test_body_content_is_untouched():
    """Not one word of any article may change — this only affects crawler instructions."""
    out = noindex.add_noindex(PAGE)
    assert BODY in out


def test_a_page_with_no_head_is_left_alone():
    orphan = "<html><body><p>x</p></body></html>"
    assert noindex.add_noindex(orphan) == orphan


# --- selection --------------------------------------------------------------


def test_curated_pages_are_never_targeted():
    """
    The invariant. Anything in sitemap.xml is advertised to Google on purpose; de-indexing
    it would be the precise opposite of what this script is for.
    """
    curated = noindex.curated_slugs()
    assert curated, "sitemap parsed as empty — selection would target the whole corpus"
    assert set(noindex.targets()).isdisjoint(curated)


def test_core_pages_are_never_targeted():
    """
    about/contact/privacy are excluded from the sitemap as a navigation decision, not a
    quality judgement. De-indexing them would hide the pages that make the site look
    legitimate — including the affiliate disclosure and privacy policy.
    """
    assert set(noindex.targets()).isdisjoint(noindex.NEVER_TOUCH)


def test_selection_is_derived_from_the_live_sitemap():
    """If this ever reads from a hardcoded list instead, the two can drift silently."""
    import inspect

    src = inspect.getsource(noindex.curated_slugs)
    assert "sitemap" in src.lower()


def test_targets_are_real_files():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in noindex.targets()[:20]:
        assert os.path.exists(os.path.join(here, name)), name


# --- the live corpus --------------------------------------------------------


def test_no_advertised_page_carries_noindex():
    """
    The failure that would matter most in production: a page in the sitemap that also says
    noindex tells Google two opposite things and wastes the crawl.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for slug in sorted(noindex.curated_slugs()):
        path = os.path.join(here, slug)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            assert "noindex" not in fh.read().lower(), f"{slug} is advertised AND noindexed"


# --- convergence (review 2026-09-02) ----------------------------------------


def _fake_corpus(tmp_path, monkeypatch, curated, uncurated):
    """A throwaway corpus: pages on disk plus a sitemap naming the curated ones."""
    for name in curated + uncurated:
        (tmp_path / name).write_text(PAGE, encoding="utf-8")
    locs = "".join(f"<url><loc>https://x.example/{n}</loc></url>" for n in curated)
    (tmp_path / "sitemap.xml").write_text(
        f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>',
        encoding="utf-8")
    monkeypatch.setattr(noindex, "HERE", str(tmp_path))
    monkeypatch.setattr(noindex, "SITEMAP", str(tmp_path / "sitemap.xml"))


def test_a_page_promoted_into_the_sitemap_loses_its_tag(tmp_path, monkeypatch):
    """
    The hole the first version had: a page that carried the tag while uncurated kept it
    after promotion, because only uncurated pages were ever visited. Now every run makes
    every page match the sitemap.
    """
    _fake_corpus(tmp_path, monkeypatch, curated=["promoted.html"], uncurated=["still-out.html"])
    (tmp_path / "promoted.html").write_text(noindex.add_noindex(PAGE), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["apply_noindex_to_uncurated.py"])
    assert noindex.main() == 0
    assert noindex.TAG not in (tmp_path / "promoted.html").read_text(encoding="utf-8")
    assert noindex.TAG in (tmp_path / "still-out.html").read_text(encoding="utf-8")


def test_remove_reaches_curated_pages_too(tmp_path, monkeypatch):
    """`--remove` must be the full reversal it claims, wherever the tag ended up."""
    _fake_corpus(tmp_path, monkeypatch, curated=["in.html"], uncurated=["out.html"])
    for n in ("in.html", "out.html"):
        (tmp_path / n).write_text(noindex.add_noindex(PAGE), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["apply_noindex_to_uncurated.py", "--remove"])
    assert noindex.main() == 0
    for n in ("in.html", "out.html"):
        assert noindex.TAG not in (tmp_path / n).read_text(encoding="utf-8"), n


def test_core_pages_are_never_visited_even_by_remove(tmp_path, monkeypatch):
    """404.html carries its own noindex on purpose; no mode may strip it."""
    _fake_corpus(tmp_path, monkeypatch, curated=[], uncurated=["a.html"])
    (tmp_path / "404.html").write_text(noindex.add_noindex(PAGE), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["apply_noindex_to_uncurated.py", "--remove"])
    assert noindex.main() == 0
    assert noindex.TAG in (tmp_path / "404.html").read_text(encoding="utf-8")
