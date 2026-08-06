"""
Tests for fix_dead_affiliate_links.py.

Two failure modes matter. Removing a link that is fine would silently destroy working
affiliate revenue — so the live-ASIN case is asserted first and hardest. And a repair that
invents a replacement ASIN would violate repo rule 5; the only correct outcome for a dead
link is that the anchor disappears and the reader's words stay.

The corpus test at the bottom guards the invariant going forward.
"""
import glob

import fix_dead_affiliate_links as F

LIVE = "B00JRMQIJ4"     # verified HTTP 200 on 2026-08-05
DEAD = "B0D1234567"     # fabricated placeholder


def _a(asin, text="Littmann stethoscope"):
    return (f'<p>Try the <a href="https://www.amazon.com/dp/{asin}?tag=ariacapital-20" '
            f'rel="nofollow">{text}</a> for night shift.</p>')


def test_a_working_link_is_left_completely_alone():
    html = _a(LIVE)
    out, removed = F.strip_dead(html)
    assert out == html
    assert removed == {}


def test_a_dead_link_loses_the_anchor_and_keeps_the_words():
    out, removed = F.strip_dead(_a(DEAD))
    assert removed == {DEAD: 1}
    assert "Littmann stethoscope" in out          # the prose survives
    assert "amazon.com" not in out                 # the link does not
    assert "<a " not in out


def test_the_repair_never_invents_a_replacement_asin():
    # Repo rule 5: losing a link is acceptable, inventing one is not.
    out, _ = F.strip_dead(_a(DEAD))
    for asin in F.DEAD_ASINS:
        assert asin not in out
    assert "/dp/" not in out


def test_mixed_page_keeps_the_good_link_and_drops_only_the_dead_one():
    html = _a(LIVE, "good book") + _a(DEAD, "bad book")
    out, removed = F.strip_dead(html)
    assert removed == {DEAD: 1}
    assert LIVE in out and DEAD not in out
    assert "good book" in out and "bad book" in out


def test_it_is_idempotent():
    once, _ = F.strip_dead(_a(DEAD))
    twice, removed = F.strip_dead(once)
    assert twice == once
    assert removed == {}


def test_no_article_still_links_a_known_dead_asin():
    """After the repair has run, this is the invariant that must hold forever."""
    offenders = []
    for path in sorted(glob.glob("*.html")):
        html = open(path, encoding="utf-8").read()
        if "amazon.com" not in html:
            continue
        for asin in F.DEAD_ASINS:
            if f"/dp/{asin}" in html or f"/gp/product/{asin}" in html:
                offenders.append(f"{path}:{asin}")
    assert not offenders, f"dead affiliate links still live: {offenders}"
