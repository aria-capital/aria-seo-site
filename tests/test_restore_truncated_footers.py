"""
Tests for restore_truncated_footers.py.

The repair writes bytes back into three live pages, so what matters is the guard, not the
happy path: a canonical is only ever applied when the file already contains its opening
bytes exactly. Anything else must be skipped rather than approximated — this is the same
class of repair that once deleted 171 recoverable newsletter forms by excising instead of
restoring.
"""
import os

import restore_truncated_footers as R

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANONICAL = R.CANONICAL_FOOTERS[1]  # the dmca-policy.html variant, a short one
TRUNCATED = CANONICAL[:-40]         # cut somewhere inside the link list

BODY = "<html><head></head><body><p>article</p>\n"
AFTER = "\n\n<!-- newsletter -->\n<div>keep me</div>\n</body></html>"


def test_a_truncated_footer_is_completed_from_its_canonical():
    out = R.restore(BODY + TRUNCATED + AFTER)
    assert out == BODY + CANONICAL + AFTER


def test_everything_after_the_fragment_is_preserved():
    out = R.restore(BODY + TRUNCATED + AFTER)
    assert "<div>keep me</div>" in out
    assert out.count("<div>keep me</div>") == 1


def test_a_balanced_footer_is_left_alone():
    assert R.restore(BODY + CANONICAL + AFTER) is None


def test_a_fragment_that_matches_no_canonical_is_skipped():
    """No guessing: an unrecognised footer is reported, not approximated."""
    assert R.restore(BODY + "<footer>\n<p>something nobody has seen before" + AFTER) is None


def test_restore_is_idempotent():
    once = R.restore(BODY + TRUNCATED + AFTER)
    assert once is not None
    assert R.restore(once) is None


def test_an_unclosed_footer_followed_by_a_complete_one_is_still_found():
    """
    nurse-real-estate-investing.html: a naive "is there a </footer> after this?" lookahead
    finds the SECOND footer's closing tag and declares the first one closed.
    """
    html = BODY + "<footer>\n<p>first</p>" + AFTER + "\n<footer>\n<p>second</p>\n</footer>\n"
    span = R.truncated_footer_span(html)
    assert span is not None
    assert html[span[0]:span[1]] == "<footer>\n<p>first</p>"


def test_span_is_none_when_footers_balance():
    assert R.truncated_footer_span(BODY + CANONICAL + AFTER) is None


# --- corpus-level invariant --------------------------------------------------


def test_no_page_has_an_unclosed_footer():
    """
    Two of the three damaged pages scored as perfectly clean on both gates, because
    html_severity() only counted <div>. If that gap reopens, this fails.
    """
    unbalanced = {}
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        if html.count("<footer") != html.count("</footer>"):
            unbalanced[name] = (html.count("<footer"), html.count("</footer>"))
    assert unbalanced == {}
