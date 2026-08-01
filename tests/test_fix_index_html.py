"""
Tests for fix_index_html.py.

The homepage was the one page check_site_integrity.py failed on. The repair rebuilds some
truncated cards and discards others, so the rules deciding which is which are the whole
risk: rebuild too eagerly and the grid gains a card linking nowhere, or a duplicate.
"""
import os

import pytest

import fix_index_html as F

TERM = F.GRID_TERMINUS


def _page(cards, extra_links=""):
    return (
        "<html><head></head><body>\n"
        '<div class="section">\n  <div class="container">\n    <div class="grid">\n'
        + cards
        + extra_links
        + f"{TERM} -->\n<div>newsletter</div>\n</body></html>"
    )


def _card(href, title="T", closed=True):
    body = f'<div class="article-card"><h3><a href="{href}">{title}</a></h3><p>Desc.</p>'
    return body + "</div>\n" if closed else body + "\n"


@pytest.fixture
def site(tmp_path):
    for name in ("real.html", "other.html"):
        (tmp_path / name).write_text("<html></html>", encoding="utf-8")
    return tmp_path


def test_healthy_cards_are_untouched(site):
    html = _page(_card("real.html"))
    out, stats = F.repair(html, str(site))
    assert stats["healthy"] == 1 and stats["rebuilt"] == 0 and stats["discarded"] == 0
    assert '<a href="real.html">T</a>' in out


def test_truncated_card_with_intact_anchor_is_rebuilt(site):
    html = _page(_card("real.html", closed=False))
    out, stats = F.repair(html, str(site))
    assert stats["rebuilt"] == 1
    assert '<div class="article-card"><h3><a href="real.html">T</a></h3></div>' in out
    assert "<p>Desc." not in out, "the partial paragraph must be discarded, not kept"


def test_card_with_no_recoverable_anchor_is_discarded(site):
    html = _page('<div class="article-card"><h3><a href\n')
    out, stats = F.repair(html, str(site))
    assert stats["discarded"] == 1 and stats["rebuilt"] == 0
    assert "article-card" not in out


def test_card_with_a_partial_href_is_discarded_not_guessed(site):
    html = _page('<div class="article-card"><h3><a href="rea\n')
    _, stats = F.repair(html, str(site))
    assert stats["discarded"] == 1


def test_card_linking_to_a_missing_file_is_discarded(site):
    """Rebuilding would put a card on the homepage pointing at a 404."""
    html = _page(_card("does-not-exist.html", closed=False))
    out, stats = F.repair(html, str(site))
    assert stats["discarded"] == 1
    assert "does-not-exist.html" not in out


def test_card_whose_href_appears_elsewhere_is_discarded(site):
    """Rebuilding a duplicate would show the same article twice in the grid."""
    html = _page(_card("real.html", closed=False), extra_links='<a href="real.html">dup</a>\n')
    _, stats = F.repair(html, str(site))
    assert stats["discarded"] == 1, "a href seen twice must not be rebuilt"


def test_grid_wrappers_are_closed(site):
    html = _page(_card("real.html"))
    out, stats = F.repair(html, str(site))
    assert stats["grid_closed"] == 3
    import re
    assert len(re.findall(r"<div\b", out)) == out.count("</div>")


def test_grid_is_closed_before_the_newsletter_block(site):
    """The newsletter must end up a sibling after the section, not a child of .grid."""
    out, _ = F.repair(_page(_card("real.html")), str(site))
    assert out.index(F.GRID_CLOSE.strip()[:12]) < out.index(TERM)


def test_footer_is_restored(site):
    out, stats = F.repair(_page(_card("real.html")), str(site))
    assert stats["footer_added"] == 1
    assert out.count("</footer>") == 1


def test_existing_footer_is_not_duplicated(site):
    html = _page(_card("real.html")).replace("</body>", "<footer>f</footer></body>")
    out, stats = F.repair(html, str(site))
    assert stats["footer_added"] == 0 and out.count("</footer>") == 1


def test_missing_grid_terminus_aborts_rather_than_guessing(site):
    with pytest.raises(AssertionError):
        F.repair("<html><body>no terminus</body></html>", str(site))


def test_duplicate_grid_terminus_aborts(site):
    html = _page(_card("real.html")) + TERM
    with pytest.raises(AssertionError):
        F.repair(html, str(site))


# --- the live homepage ------------------------------------------------------


def test_live_index_html_is_clean():
    """
    The invariant this script exists to establish, asserted against the real homepage.
    check_index() also verifies every card link resolves to a file that exists.
    """
    from check_site_integrity import check_index, html_severity

    with open(F.INDEX, encoding="utf-8") as fh:
        html = fh.read()

    sev = html_severity(html)
    assert sev["div_delta"] == 0
    assert sev["unterminated"] is False
    assert html.count("</footer>") == 1
    assert check_index() == []
