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

    Asserted over is_clinical(), NOT over the slug list. Measured 2026-09-02, the slug-only
    version of this test was green while five dose-bearing pages carried no disclaimer at
    all — among them a dosage-calculation guide with 39 dose expressions and a paediatric
    dosing guide with 28 — because none of their filenames contained a listed word. A test
    that defines its own population by filename cannot see the pages the filename misses.
    """
    import os

    files = []
    for name in sorted(os.listdir(A.HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(A.HERE, name), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if A.is_clinical(name, text):
            files.append((name, text))
    assert files, "no clinical pages found"

    missing = [n for n, t in files if not A.HAS_DISCLAIMER.search(t)]
    assert missing == [], f"clinical pages with no disclaimer: {missing}"


def test_a_dose_bearing_page_is_clinical_even_when_its_filename_says_nothing():
    """The regression that mattered: content decides, not the slug."""
    doses = "<p>Give 5 mg IV push, then 10 mg, then 250 mcg for the patient.</p>"
    assert A.is_clinical("totally-innocuous-name.html", "<html><body>" + doses + "</body></html>")
    assert not A.is_clinical("zero-based-budgeting-guide.html", "<html><body><p>Save 500 a month.</p></body></html>")


def test_consumer_health_prose_is_not_mistaken_for_a_clinical_page():
    """A fitness article quoting melatonin 0.5-3 mg is health content, but DISCLAIMER is
    addressed to licensed clinicians and would read as nonsense there. It also already
    carries its own consumer disclaimer, which HAS_DISCLAIMER must recognise."""
    page = ("<html><body><p>Melatonin 0.5 mg, magnesium 400 mg, vitamin D 25 mcg.</p>"
            "<p>General fitness information only. Consult a healthcare provider "
            "before starting a new exercise program.</p></body></html>")
    assert A.HAS_DISCLAIMER.search(page)
    assert A.add_disclaimer(page) is None


def test_ordinary_clinical_prose_does_not_count_as_a_disclaimer():
    """`verify with` and `clinical judgment` appear in normal body copy. Counting them was a
    false green: the paediatric dosing guide was credited with a disclaimer solely because it
    said "Always verify with actual weight as soon as possible"."""
    assert not A.HAS_DISCLAIMER.search("<p>Always verify with actual weight as soon as possible.</p>")
    assert not A.HAS_DISCLAIMER.search("<p>This requires clinical judgment at the bedside.</p>")
