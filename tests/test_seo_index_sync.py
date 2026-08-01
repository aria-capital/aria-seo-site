"""
Tests for seo_index_sync.py — the orphan-article fixer.

It rewrites index.html, so its "only ADDS, never deletes, safe to run repeatedly"
promise is the thing worth pinning. The card builder also interpolates article
titles and descriptions straight into markup, which makes escaping a correctness
issue rather than a cosmetic one.
"""
import os
import re

import pytest

import seo_index_sync as sync


# --- card metadata ----------------------------------------------------------


def test_title_is_extracted():
    assert sync.extract_title("<html><title>Real Title</title></html>", "x.html") == "Real Title"


def test_title_entities_are_unescaped():
    assert sync.extract_title("<title>A &amp; B</title>", "x.html") == "A & B"


def test_missing_title_falls_back_to_humanized_filename():
    assert sync.extract_title("<html></html>", "nurse-pay-guide.html") == "Nurse Pay Guide"


def test_empty_title_falls_back_to_filename():
    assert sync.extract_title("<title>   </title>", "nurse-pay.html") == "Nurse Pay"


def test_description_is_extracted():
    doc = '<meta name="description" content="A guide.">'
    assert sync.extract_desc(doc) == "A guide."


def test_missing_description_uses_default():
    assert sync.extract_desc("<html></html>").startswith("A practical, no-fluff guide")


# --- tagging ----------------------------------------------------------------


@pytest.mark.parametrize("name,label", [
    ("crna-school-guide.html", "CRNA"),
    ("ventilator-modes-icu-nurses-2026.html", "ICU"),
    ("travel-nurse-pay-2026.html", "TRAVEL"),
    ("amazon-kdp-log-books.html", "KDP"),
    ("passive-income-ideas.html", "INCOME"),
    ("roth-ira-for-nurses.html", "FINANCE"),
    ("best-nursing-shoes.html", "GEAR"),
    ("night-shift-survival.html", "NURSING"),
])
def test_tag_rules_map_slugs_to_labels(name, label):
    assert sync.pick_tag(name)[1] == label


def test_unmatched_slug_gets_the_default_tag():
    assert sync.pick_tag("sourdough-bread.html") == sync.DEFAULT_TAG


def test_first_matching_rule_wins():
    """Rule order is load-bearing: CRNA is checked before the finance rules."""
    assert sync.pick_tag("crna-salary-2026.html")[1] == "CRNA"


# --- card markup ------------------------------------------------------------


def test_card_is_balanced_and_links_to_the_article():
    card = sync.build_card("guide.html", "Title", "Desc")
    assert card.count("<a ") == card.count("</a>")
    assert 'href="guide.html"' in card


def test_card_escapes_markup_in_the_title():
    """An unescaped title would let article content break index.html."""
    card = sync.build_card("g.html", '<script>x</script>', "Desc")
    assert "<script>" not in card
    assert "&lt;script&gt;" in card


def test_card_escapes_quotes_in_the_description():
    card = sync.build_card("g.html", "T", 'He said "hi"')
    assert '&quot;' in card


def test_long_descriptions_are_truncated():
    card = sync.build_card("g.html", "T", "word " * 100)
    assert "…" in card
    assert len(card) < 600


# --- index rewriting --------------------------------------------------------

SECTION = sync.build_section([sync.build_card("a.html", "A", "d")])


def test_section_is_inserted_before_the_newsletter_block():
    index = '<html><body><div class="newsletter">n</div></body></html>'
    out = sync.upsert_section(index, SECTION)
    assert out.index(sync.SECTION_START) < out.index('<div class="newsletter">')


def test_section_falls_back_to_body_close():
    index = "<html><body>content</body></html>"
    out = sync.upsert_section(index, SECTION)
    assert sync.SECTION_START in out
    assert out.index(sync.SECTION_START) < out.index("</body>")


def test_upsert_replaces_an_existing_section_rather_than_appending():
    index = "<html><body>" + SECTION + "</body></html>"
    new_section = sync.build_section([sync.build_card("b.html", "B", "d")])
    out = sync.upsert_section(index, new_section)

    assert out.count(sync.SECTION_START) == 1, "a second run must not stack sections"
    assert "b.html" in out and "a.html" not in out


def test_upsert_is_idempotent():
    index = '<html><body><div class="newsletter">n</div></body></html>'
    once = sync.upsert_section(index, SECTION)
    assert sync.upsert_section(once, SECTION) == once


def test_upsert_preserves_existing_content():
    index = '<html><body><p>keep me</p><div class="newsletter">n</div></body></html>'
    out = sync.upsert_section(index, SECTION)
    assert "<p>keep me</p>" in out


# --- link discovery ---------------------------------------------------------


def test_linked_articles_are_discovered():
    assert sync.linked_in_index('<a href="nurse-pay-2026.html">x</a>') == {"nurse-pay-2026.html"}


def test_link_discovery_finds_underscored_filenames():
    """
    The href pattern used to allow only [a-z0-9-], so privacy_policy.html — the one
    underscored filename in the corpus — read as unlinked and got re-added as an orphan
    card on every run, making the script non-idempotent.
    """
    assert sync.linked_in_index('<a href="privacy_policy.html">x</a>') == {"privacy_policy.html"}


def test_link_discovery_finds_mixed_case_filenames():
    assert sync.linked_in_index('<a href="README.html">x</a>') == {"README.html"}


def test_link_discovery_ignores_external_and_anchored_links():
    """Only local files count — an off-site URL is not an article the index has covered."""
    html = (
        '<a href="https://example.test/other.html">x</a>'
        '<a href="sub/dir/page.html">y</a>'
        '<a href="page.html#section">z</a>'
        '<a href="real-article.html">ok</a>'
    )
    assert sync.linked_in_index(html) == {"real-article.html"}


def test_link_discovery_is_idempotent_against_the_live_index():
    """Every article index.html links to must be seen, or the next run duplicates its card."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "index.html"), encoding="utf-8") as fh:
        index = fh.read()
    linked = sync.linked_in_index(index)
    for href in re.findall(r'href="([^":/?#]+\.html)"', index):
        assert href in linked, href
