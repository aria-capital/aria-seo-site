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
