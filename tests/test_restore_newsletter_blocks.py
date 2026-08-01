"""
Tests for restore_newsletter_blocks.py.

The newsletter block is the site's email list. The truncation repair discarded 171 of them
as if they were promo boilerplate. Restoring is only safe because each damaged fragment is a
byte-exact prefix of a known template — these tests pin that the prefix check is what gates
the write, so a fragment that does not match is refused rather than completed with a guess.
"""
import restore_newsletter_blocks as R

H1 = "Get The ICU Notebook Newsletter"
S1 = "Clinical tools and career insights for ICU nurses. One email per week, no fluff."
H2 = "Get the ARIA Finance Weekly"
S2 = "Practical money strategies, one email per week. No fluff."


def _full(h, s):
    return R.TRIPLES[(h, s)].replace("{H}", h).replace("{S}", s)


def test_icu_fragment_is_completed_to_the_icu_template():
    full = _full(H1, S1)
    out = R.render(full[:400])
    assert out == full
    assert "<!-- /email-capture -->" in out


def test_aria_fragment_is_completed_to_the_aria_template():
    full = _full(H2, S2)
    out = R.render(full[:400])
    assert out == full


def test_aria_template_has_no_end_comment():
    """Settled from git: all 25 ancestors end at </div> with no end comment."""
    assert not _full(H2, S2).rstrip().endswith("<!-- /email-capture -->")


def test_icu_template_has_the_end_comment():
    assert _full(H1, S1).rstrip().endswith("<!-- /email-capture -->")


def test_completed_block_is_div_balanced():
    import re

    for h, s in ((H1, S1), (H2, S2)):
        block = _full(h, s)
        assert len(re.findall(r"<div\b", block)) == block.count("</div>")
        assert block.count("<form") == block.count("</form>")


def test_unknown_heading_is_refused_not_guessed():
    full = _full(H1, S1).replace(H1, "Some Other Newsletter")
    assert R.render(full[:400]) is None


def test_fragment_that_is_not_a_prefix_is_refused():
    """A fragment whose bytes diverge from the template must never be completed."""
    full = _full(H1, S1)
    tampered = full[:300].replace("beehiiv.com", "evil.example.com")
    assert R.render(tampered) is None


def test_truncated_before_the_heading_is_refused():
    assert R.render(R.NL_START) is None


def test_malformed_heading_line_is_refused():
    full = _full(H1, S1).replace(R.HP, "  <p>")
    assert R.render(full[:400]) is None


def test_block_complete_detects_a_closed_block():
    assert R.block_complete("<body>" + _full(H1, S1) + "</body>")


def test_block_complete_rejects_an_unclosed_block():
    assert not R.block_complete("<body>" + _full(H1, S1)[:300])


def test_block_complete_is_false_when_absent():
    assert not R.block_complete("<html><body><p>no newsletter</p></body></html>")


# --- corpus-level invariant -------------------------------------------------


def test_every_page_that_has_a_newsletter_block_has_a_complete_one():
    """A half-written signup form captures no emails and breaks the page below it."""
    import os

    offenders = []
    for name in sorted(os.listdir(R.HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(R.HERE, name), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if R.NL_START in text and not R.block_complete(text):
            offenders.append(name)
    assert offenders == []
