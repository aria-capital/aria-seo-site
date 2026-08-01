"""
Tests for fix_truncated_articles.py.

The rule that matters most here is the one the analysis got wrong twice: only the INNERMOST
unclosed <div> may be discarded, and only when it is a short non-wrapper leaf. Cascading the
excision outward destroys complete sibling content. That is pinned below, along with the
block-validation and the closing behaviour.
"""
import pytest

import fix_truncated_articles as F


def _b(s):
    return s.encode("utf-8")


def _t(b):
    return b.decode("utf-8")


HEAD = "<html><head></head><body>\n"


# --- no-ops -----------------------------------------------------------------


def test_complete_document_is_a_no_op():
    assert F.repair(_b(HEAD + "<p>done</p></body></html>")) is None


def test_repair_is_idempotent():
    once = F.repair(_b(HEAD + "<div><p>cut"))
    assert F.repair(once) is None


def test_nul_padded_but_complete_file_only_loses_the_padding():
    """Some files were NUL-padded rather than truncated; the document underneath is fine."""
    out = F.repair(_b(HEAD + "<p>x</p></body></html>") + b"\x00" * 40)
    assert out is not None
    assert b"\x00" not in out
    assert _t(out).rstrip().endswith("</html>")


# --- closing ----------------------------------------------------------------


def test_document_is_closed():
    out = _t(F.repair(_b(HEAD + "<p>cut off mid")))
    assert out.rstrip().endswith("</body>\n</html>")


def test_half_written_tag_is_dropped():
    """An unterminated tag would swallow every closing tag appended after it."""
    out = _t(F.repair(_b(HEAD + '<p>text</p>\n<div class="x" styl')))
    assert "styl" not in out
    assert out.rstrip().endswith("</html>")


def test_unterminated_attribute_is_dropped():
    out = _t(F.repair(_b(HEAD + '<p>ok</p>\n<div style="color:#fff;display:fl')))
    assert "display:fl" not in out
    from check_site_integrity import html_severity
    assert html_severity(out)["unterminated_attr"] == 0


def test_unclosed_script_is_closed():
    out = _t(F.repair(_b(HEAD + "<script>\nfunction calc(){ var x = 1")))
    assert out.count("<script") == out.count("</script>")


# --- the innermost-only rule ------------------------------------------------


def test_innermost_leaf_fragment_is_discarded():
    out = _t(F.repair(_b(HEAD + '<div class="container"><p>keep me</p><div class="promo">cut')))
    assert "keep me" in out
    assert "cut" not in out


def test_wrapper_div_is_closed_never_discarded():
    """A container holds real content; closing preserves it, discarding destroys it."""
    out = _t(F.repair(_b(HEAD + '<div class="container"><p>important body text</p>')))
    assert "important body text" in out
    assert out.count("</div>") >= 1


def test_outer_siblings_survive_when_the_innermost_is_excised():
    """Regression: cascading excision outward destroyed 4 complete sibling cards."""
    html = (HEAD + '<div class="container">'
            '<div class="topic-card">one</div>'
            '<div class="topic-card">two</div>'
            '<div class="topic-card">three</div>'
            '<div class="topic-card">partial frag')
    out = _t(F.repair(_b(html)))
    for kept in ("one", "two", "three"):
        assert kept in out, f"complete sibling {kept!r} was destroyed"


def test_large_unclosed_div_is_closed_not_discarded():
    """Only short leaves are discarded; a big block is real content."""
    big = "x" * (F.LEAF_MAX + 500)
    out = _t(F.repair(_b(HEAD + f'<div class="promo">{big}')))
    assert big in out


def test_result_is_div_balanced():
    from check_site_integrity import html_severity

    for html in (
        HEAD + "<div><div><p>cut",
        HEAD + '<div class="container"><div class="promo">frag',
        HEAD + "<p>plain cut",
    ):
        assert html_severity(_t(F.repair(_b(html))))["div_delta"] == 0


# --- block validation -------------------------------------------------------


def test_damaged_trailing_block_is_excised():
    html = HEAD + "<p>body</p>\n<!-- gumroad-cta --><div>partial promo"
    out = _t(F.repair(_b(html)))
    assert "<p>body</p>" in out
    assert "partial promo" not in out


def test_intact_trailing_block_is_preserved():
    html = HEAD + "<p>body</p>\n<!-- gumroad-cta --><div>promo</div><!-- /gumroad-cta -->"
    out = _t(F.repair(_b(html)))
    assert "promo" in out and "<!-- /gumroad-cta -->" in out


def test_affiliate_terminator_matches_the_injector_output():
    """inject_affiliate_links emits '<!-- /AFFILIATE-CTA:sofi -->', not a bare '-->'."""
    terminator = dict((n, t) for n, _, t in F.BLOCKS)["affiliate"]
    assert "<!-- /AFFILIATE-CTA:sofi -->".startswith(terminator)


def test_block_intact_uses_div_matching_when_terminator_is_none():
    text = '<div id="related-articles"><ul><li>a</li></ul></div>TAIL'
    assert F.block_intact(text, 0, None, len(text))
    assert not F.block_intact('<div id="related-articles"><ul><li>a', 0, None, 36)


def test_unclosed_divs_reports_outermost_first():
    text = '<div class="a"><div class="b">'
    assert F.unclosed_divs(text) == [0, text.index('<div class="b"')]


# --- corpus-level invariant -------------------------------------------------


def test_no_article_is_truncated():
    """The invariant this script exists to establish, across the whole live corpus."""
    import os

    from check_site_integrity import html_severity

    offenders = []
    for name in sorted(os.listdir(F.HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(F.HERE, name), encoding="utf-8", errors="replace") as fh:
            if html_severity(fh.read())["unterminated"]:
                offenders.append(name)
    assert offenders == []
