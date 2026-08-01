"""
Tests for add_clinical_disclaimers.py.

Two failure modes matter: leaving a drug-dosing page with no disclaimer, and stacking a
second disclaimer onto the 498 pages that already have one. The corpus-level test at the
bottom is the one that actually guards the invariant going forward.
"""
import add_clinical_disclaimers as A

BODY = "<html><head></head><body><h1>Rocuronium</h1><p>Dosing.</p>"
TRAILING = '<div id="related-articles">r</div></body></html>'
PAGE = BODY + TRAILING


def test_disclaimer_is_added_to_a_page_without_one():
    out = A.add_disclaimer(PAGE)
    assert out is not None
    assert "not medical advice" in out
    assert "verify doses independently" in out


def test_disclaimer_lands_at_the_end_of_the_body_not_after_trailing_blocks():
    out = A.add_disclaimer(PAGE)
    assert out.index("not medical advice") < out.index('<div id="related-articles"')
    assert out.index("<p>Dosing.</p>") < out.index("not medical advice")


def test_page_with_an_existing_disclaimer_is_skipped():
    page = BODY + "<p>This is general educational information, not medical advice.</p>" + TRAILING
    assert A.add_disclaimer(page) is None


def test_alternative_disclaimer_wordings_are_recognised():
    """The corpus uses several variants; none should get a second disclaimer stacked on."""
    for phrasing in (
        "for educational purposes only",
        "general educational information for licensed clinicians",
        "not a substitute for clinical judgment",
        "follow your institutional protocol",
        "consult your pharmacist",
    ):
        page = BODY + f"<p>{phrasing}.</p>" + TRAILING
        assert A.add_disclaimer(page) is None, phrasing


def test_adding_is_idempotent():
    once = A.add_disclaimer(PAGE)
    assert A.add_disclaimer(once) is None


def test_page_with_no_trailing_block_is_left_alone():
    """No reliable insertion point, so skip rather than guess and corrupt the page."""
    assert A.add_disclaimer("<html><head></head><body><p>x</p>") is None


def test_disclaimer_is_html_balanced():
    import re

    assert A.DISCLAIMER.count("<p") == A.DISCLAIMER.count("</p>")
    assert len(re.findall(r"<div\b", A.DISCLAIMER)) == A.DISCLAIMER.count("</div>")


def test_insertion_point_picks_the_earliest_trailing_block():
    text = "body<footer>f</footer><!-- ICU Notebook -->"
    assert A.insertion_point(text) == text.index("<footer")


def test_clinical_slug_matching():
    assert A.CLINICAL_SLUG.search("rocuronium-vs-vecuronium-icu-nurses-2026.html")
    assert A.CLINICAL_SLUG.search("vasopressor-titration-guide-icu-2026.html")
    assert not A.CLINICAL_SLUG.search("zero-based-budgeting-guide.html")


# --- corpus-level invariant -------------------------------------------------


def test_every_clinical_page_carries_a_disclaimer():
    """
    The point of the script. If a future bulk generation adds a drug article without a
    disclaimer, this fails rather than shipping it.
    """
    import os

    files = [f for f in sorted(os.listdir(A.HERE))
             if f.endswith(".html") and A.CLINICAL_SLUG.search(f)]
    assert files, "no clinical pages found"

    missing = []
    for name in files:
        with open(os.path.join(A.HERE, name), encoding="utf-8", errors="replace") as fh:
            if not A.HAS_DISCLAIMER.search(fh.read()):
                missing.append(name)
    assert missing == []
