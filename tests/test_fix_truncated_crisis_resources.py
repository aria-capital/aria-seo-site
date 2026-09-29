"""
Tests for fix_truncated_crisis_resources.py, plus the corpus guard that outlives the repair.

The guard asserts the one invariant that matters here and would have caught this years earlier:

    a sentence that offers the reader a crisis resource must NAME that resource completely.

It is deliberately narrower than "no truncated paragraph anywhere". Twenty-seven pages carry a
truncated closing attribution paragraph and only two of them endanger anyone; a guard that went
red on all 27 would be red on every build from day one, and CLAUDE.md is explicit about what
happens to a permanently-red gate — everyone learns to ignore it, which is the failure mode that
let the truncation bug run for months. So this guard covers the safety-critical subclass, is
green today, and stays green only while every crisis sentence is complete. The other 25 are
recorded in CLAUDE.md as an open class, not enforced here.

Note what is NOT asserted: that a page must contain a crisis resource at all. That would be a
content mandate, and adding crisis copy to pages that never had it is the owner's call. The
guard only says: IF a page starts to offer one, it must finish.
"""
import glob
import os
import re

import pytest

import fix_truncated_crisis_resources as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CORPUS = None


def corpus():
    global _CORPUS
    if _CORPUS is None:
        out = []
        for p in sorted(glob.glob(os.path.join(REPO, "*.html"))):
            with open(p, encoding="utf-8", errors="replace") as fh:
                out.append((os.path.basename(p), fh.read()))
        _CORPUS = out
    return _CORPUS


# "contact / call / reach out to ..." opening a crisis offer, then everything up to the next
# tag. The tail is NOT length-capped: capping it was the bug in the first version of this file.
CRISIS_OFFER = re.compile(
    r"(?:in crisis|mental health crisis|thoughts of self-harm|suicidal)[^<.]{0,140}?"
    r"(?:contact|call|reach out to|text)\s+(?:the\s+)?([^<]*)",
    re.I,
)


def incomplete_crisis_offers(text):
    """Crisis offers that run into a tag boundary without finishing the sentence.

    The property measured is TRUNCATION, not the presence of a phone number, and the first
    version of this detector got that wrong in both directions at once — a useful demonstration
    of why both controls are mandatory:

      FALSE POSITIVE. It demanded a phone number or lifeline name, so it reddened
      "...are signs to reach out to a mental health professional directly rather than treating
      this as occupational burnout alone." That is a complete, correct referral naming no
      number. It only looked broken because a 90-character window had cut the sentence — the
      detector was truncating the text and then reporting it as truncated.

      FALSE NEGATIVE. To stop it firing on the correct "(call or text 988).", it carried an
      escape hatch for any tail containing "988" — which let the live defect
      "please contact the 988 Suicide<cut>" pass clean. The needle exempted the very string
      it existed to catch.

    Measuring truncation directly is both simpler and right: a crisis sentence that stops at a
    tag boundary with no terminal punctuation was cut off, whatever resource it was naming.
    """
    bad = []
    for m in CRISIS_OFFER.finditer(text):
        tail = m.group(1).strip()
        if not re.search(r"[.!?]['\")\]”]?$", tail):
            bad.append(m.group(0).strip()[-90:])
    return bad


def test_the_corpus_is_not_empty():
    """Positive control. Without it, every scan below passes by measuring nothing."""
    assert len(corpus()) > 1000, "article glob found almost nothing — the guard is blind"


def test_the_corpus_actually_contains_crisis_offers():
    """Second positive control, and the one that matters more: prove the DETECTOR matches real
    content. If the regex stopped matching, the scan below would be green and meaningless."""
    hits = [n for n, t in corpus() if CRISIS_OFFER.search(t)]
    assert len(hits) >= 4, f"expected several pages offering a crisis resource, found {hits}"


def test_every_edit_names_a_real_file():
    for path, _old, _new, _why, _src in F.EDITS:
        assert os.path.exists(os.path.join(REPO, path)), f"{path} does not exist"


def test_the_repair_is_idempotent_against_the_live_tree():
    for path, old, _new, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert fh.read().count(old) == 0, f"{path}: pre-repair text is still present"


def test_every_replacement_landed():
    for path, _old, new, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert new in fh.read(), f"{path}: corrected wording is missing"


# --- the guard that outlives the repair ----------------------------------------------------

def test_no_page_offers_a_crisis_resource_without_naming_it():
    """Corpus-wide. A page that begins 'if you are in crisis, please contact the' and stops has
    handed a reader in an emergency nothing at all."""
    offenders = []
    for name, text in corpus():
        for bad in incomplete_crisis_offers(text):
            offenders.append(f"{name}: ...{bad!r}")
    assert offenders == [], (
        "crisis offer names no resource:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("planted", [
    "If you are in crisis, please contact the\n<div id=\"related-articles\">",
    "If you are experiencing a mental health crisis, please contact the 988 Suicide\n<div>",
    "If you are in crisis, reach out to your\n<div>",
])
def test_the_guard_can_go_red_on_the_wordings_that_were_live(planted):
    """Two of these three were the live text. The detector must fire on all of them."""
    assert incomplete_crisis_offers(planted), f"detector failed on {planted[:60]!r}"


@pytest.mark.parametrize("complete", [
    "If you are in crisis, please contact the 988 Suicide and Crisis Lifeline (call or text 988).",
    "If you are struggling, contact your local crisis line or, in the US, call or text 988.",
    "In crisis, contact the 988 Suicide and Crisis Lifeline.",
    "If you are experiencing thoughts of self-harm, please contact the 988 Suicide and Crisis "
    "Lifeline (call or text 988) or the Crisis Text Line.",
    # The real sentence that the first version of this guard wrongly reddened. It names no
    # phone number and is entirely correct, so it is kept as a permanent control.
    "...thoughts of self-harm are signs to reach out to a mental health professional directly "
    "rather than treating this as occupational burnout alone.",
])
def test_the_guard_stays_silent_on_complete_offers(complete):
    """The crying-wolf control, built from wording this site already publishes. A guard that
    reddens on a correctly-written crisis sentence is a guard that gets deleted."""
    assert incomplete_crisis_offers(complete) == [], f"guard wrongly fires on {complete[:60]!r}"


def test_both_repaired_pages_now_name_the_lifeline_in_full():
    for page in ("icu-nurse-burnout-signs-prevention-2026.html",
                 "nurse-burnout-recovery-plan-2026.html"):
        with open(os.path.join(REPO, page), encoding="utf-8") as fh:
            text = fh.read()
        assert "988 Suicide and Crisis Lifeline (call or text 988).</p>" in text, page
        assert incomplete_crisis_offers(text) == [], page


def test_the_site_still_publishes_the_wording_this_repair_propagates():
    """Provenance check. If the source phrasing vanishes, the completion has lost its basis."""
    hits = [n for n, t in corpus() if "988 Suicide and Crisis Lifeline" in t]
    assert len(hits) >= 3, f"expected the full lifeline name on several pages, got {hits}"


def test_the_repaired_paragraphs_are_closed():
    """The unclosed <p> is what hid this from every gate; a repair that leaves it open
    re-creates the hiding place."""
    for page in ("icu-nurse-burnout-signs-prevention-2026.html",
                 "nurse-burnout-recovery-plan-2026.html"):
        with open(os.path.join(REPO, page), encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r'<p style="font-size:0\.85rem;color:#888">(.*?)</p>', text, re.S)
        assert m, f"{page}: the attribution paragraph is still unclosed"
