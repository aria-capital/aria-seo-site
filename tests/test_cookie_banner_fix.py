"""
Tests for fix_cookie_banner.py.

The banner landed truncated in 599 files, cut at three different points. This
pins the repair for each cut, and — most importantly — pins idempotency: the
script runs over the whole corpus, so a non-idempotent repair would stack a
second banner onto every file on the next run.
"""
from fix_cookie_banner import CANONICAL, find_region, repair

FOOTER = "<footer>f</footer>\n"
NEWSLETTER = '\n\n<!-- ICU Notebook Newsletter -- email capture -->\n<div>news</div>\n'
TAIL = "</body>\n</html>"

OPEN_TAG = (
    '<div id="cookie-banner" style="display:none;position:fixed;z-index:9999;'
    'display:flex;align-items:center;gap:10px;">'
)


def _doc(banner_region: str, after: str = NEWSLETTER) -> str:
    return f"<html><head></head><body>\n{FOOTER}{banner_region}{after}{TAIL}"


def _divs(text: str) -> int:
    import re
    return len(re.findall(r"<div\b", text)) - text.count("</div>")


# The three observed cut points.
CUT_IN_STYLE = _doc(
    "<!-- COOKIE CONSENT BANNER — GDPR/CCPA -->\n"
    '<div id="cookie-banner" style="display:none;position:fixed;z-index:9999;display:flex'
)
CUT_IN_SPAN = _doc(
    "<!-- COOKIE CONSENT BANNER — GDPR/CCPA -->\n"
    + OPEN_TAG
    + "\n  <span>We use cookies for analytics and adverti"
)
CUT_IN_SCRIPT = _doc(
    "<!-- COOKIE CONSENT BANNER — GDPR/CCPA -->\n"
    + OPEN_TAG
    + "\n  <span>ok</span>\n</div>\n<script>\n(function(){\n  tr",
    after='\n\n<div id="related-articles">r</div>\n',
)
INTACT = _doc(CANONICAL)


def test_document_without_a_banner_is_untouched():
    assert repair("<html><head></head><body><div>x</div></body></html>") is None
    assert find_region("<html></html>") is None


def test_intact_banner_is_a_no_op():
    assert repair(INTACT) is None


def test_cut_in_style_attribute_is_repaired():
    out = repair(CUT_IN_STYLE)
    assert out is not None
    assert CANONICAL in out
    # The unterminated style attribute is gone, so following markup parses again.
    assert "display:flex\n\n<!--" not in out


def test_cut_in_span_is_repaired():
    out = repair(CUT_IN_SPAN)
    assert out is not None and CANONICAL in out


def test_cut_in_script_is_repaired():
    out = repair(CUT_IN_SCRIPT)
    assert out is not None and CANONICAL in out
    assert "(function(){\n  tr\n" not in out, "the dangling script must be replaced"


def test_repair_restores_div_balance():
    for damaged in (CUT_IN_STYLE, CUT_IN_SPAN, CUT_IN_SCRIPT):
        assert _divs(repair(damaged)) == 0


def test_repair_emits_exactly_one_banner():
    for damaged in (CUT_IN_STYLE, CUT_IN_SPAN, CUT_IN_SCRIPT):
        out = repair(damaged)
        assert out.count('<div id="cookie-banner"') == 1
        assert out.count("<!-- COOKIE CONSENT BANNER") == 1
        assert out.count("<!-- END COOKIE BANNER -->") == 1


def test_repair_preserves_surrounding_content():
    """The repair must replace only the banner region, never its neighbours."""
    out = repair(CUT_IN_STYLE)
    assert FOOTER in out
    assert "<div>news</div>" in out
    assert out.endswith(TAIL)


def test_repair_preserves_content_after_a_cut_script():
    out = repair(CUT_IN_SCRIPT)
    assert '<div id="related-articles">r</div>' in out


def test_repair_is_idempotent():
    for damaged in (CUT_IN_STYLE, CUT_IN_SPAN, CUT_IN_SCRIPT):
        once = repair(damaged)
        assert repair(once) is None, "a second pass must change nothing"


def test_banner_at_end_of_file_with_no_following_sibling():
    """Nothing follows the cut, so the region runs to EOF."""
    doc = "<html><head></head><body>\n" + FOOTER + \
        '<!-- COOKIE CONSENT BANNER — GDPR/CCPA -->\n<div id="cookie-banner" style="display:no'
    out = repair(doc)
    assert out is not None and CANONICAL in out
    assert repair(out) is None
