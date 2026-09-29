"""
Tests for fix_sweep3_read_findings.py, plus the corpus guards that outlive the repair.

One guard here is a different shape from anything else in this suite, and it exists because of
how the first two edits came about. Commit 67e198da corrected a lab value on the SBAR page and
left two clauses still reasoning from the old one, so the page contradicted itself for a day.
The lesson is that a single-substring repair fixes a wrong VALUE and does nothing about a wrong
BELIEF drawn from it. So `test_no_page_calls_a_therapeutic_aptt_sub_therapeutic` checks the
whole page for agreement rather than checking the one string that was edited — a guard that
only asserted "the Background says therapeutic" would have passed all day while the Assessment
argued the opposite.
"""
import glob
import html
import os
import re

import pytest

import fix_sweep3_read_findings as F

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


def test_the_corpus_is_not_empty():
    """Positive control for every scan below."""
    assert len(corpus()) > 1000, "article glob found almost nothing — the guards are blind"


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


def test_no_edit_introduces_a_number_the_site_does_not_already_publish():
    body = "\n".join(t for _n, t in corpus())
    for path, old, new, _why, _src in F.EDITS:
        added = set(re.findall(r"\d+(?:[.,]\d+)?", new)) - set(re.findall(r"\d+(?:[.,]\d+)?", old))
        for num in added:
            assert num in body, f"{path}: {num!r} appears nowhere else on the site"


# --- the SBAR guard: a wrong BELIEF, not a wrong value --------------------------------------

APTT_VALUE = re.compile(r"PTT[^<.]{0,40}?\bwas\s+(\d{2,3})\b", re.I)
# A DEFINITE reference — "the sub-therapeutic PTT" — asserts that the known value is
# sub-therapeutic. An indefinite or conditional one — "if it's sub-therapeutic", about a draw
# that has not happened yet — asserts nothing about it.
DEFINITE_SUBTHER = re.compile(r"\bthe\s+sub-?therapeutic\b", re.I)
# The therapeutic aPTT range this site publishes on five pages.
THERAPEUTIC_LO, THERAPEUTIC_HI = 60, 100


def aptt_belief_conflicts(text):
    """Pages that state an aPTT inside the therapeutic range and then call THAT value
    sub-therapeutic.

    Scope was chosen twice. Sentence scope is too narrow: the defect this was written for spans
    three clauses nine lines apart, and a sentence-level check would have reported the page
    clean — the cross-sentence blind spot that hid the potassium concentration error, which
    CLAUDE.md says any check of this kind must not repeat. But whole-page scope was too WIDE,
    and said so on its first run: it reddened the repaired page, because a legitimate
    conditional about the next scheduled draw ("if it's sub-therapeutic") still contains the
    word. Keying on the definite article splits the two without losing the nine-line span.
    """
    bad = []
    for m in APTT_VALUE.finditer(text):
        value = int(m.group(1))
        if not (THERAPEUTIC_LO <= value <= THERAPEUTIC_HI):
            continue
        # value-adjacent ("was 78 — sub-therapeutic"), or a definite reference anywhere.
        adjacent = re.search(r"sub-?therapeutic", text[m.end():m.end() + 40], re.I)
        if adjacent or DEFINITE_SUBTHER.search(text):
            bad.append(f"states PTT {value} (therapeutic) and calls that value sub-therapeutic")
    return bad


def test_no_page_calls_a_therapeutic_aptt_sub_therapeutic():
    """Corpus-wide. This is the guard that would have caught the half-finished repair."""
    offenders = []
    for name, text in corpus():
        for bad in aptt_belief_conflicts(text):
            offenders.append(f"{name}: {bad}")
    assert offenders == [], "aPTT value and interpretation disagree:\n  " + "\n  ".join(offenders)


def test_the_sbar_guard_can_go_red_on_the_half_finished_state():
    """Plant the exact state the page was in between 67e198da and this commit: value corrected,
    inference not. A guard that only checked the corrected string would pass on this."""
    planted = ("<p>Last PTT at 1400 was 78 &mdash; therapeutic.</p>"
               "<p>demand ischemia given the sub-therapeutic PTT and his reduced EF</p>")
    assert aptt_belief_conflicts(html.unescape(planted)), "detector missed the half-finished state"


def test_the_sbar_guard_can_go_red_on_the_original_state():
    """The state before 67e198da: the value itself labelled sub-therapeutic."""
    planted = "<p>Last PTT at 1400 was 78 &mdash; sub-therapeutic.</p>"
    assert aptt_belief_conflicts(html.unescape(planted)), "detector missed the value-adjacent form"


@pytest.mark.parametrize("fine", [
    # A real sub-therapeutic PTT, correctly described. The value gate excludes it.
    "<p>Last PTT at 1400 was 42 &mdash; sub-therapeutic.</p><p>increase the heparin drip</p>",
    # A therapeutic value plus a CONDITIONAL about the next draw. This is the false positive the
    # first version of this guard produced on the repaired page, kept as a permanent control.
    "<p>Last PTT at 1400 was 78 &mdash; therapeutic.</p>"
    "<p>The 2100 PTT is due and I'd expect the provider to adjust the drip if it's "
    "sub-therapeutic.</p>",
])
def test_the_sbar_guard_stays_silent_on_correct_pages(fine):
    """Crying-wolf control. The invariant is value/interpretation agreement, not a ban on the
    word — a page may legitimately use 'sub-therapeutic' about a value it has not seen yet."""
    assert aptt_belief_conflicts(html.unescape(fine)) == []


def test_the_sbar_guard_stays_silent_on_the_repaired_page():
    with open(os.path.join(REPO, "nursing-handoff-shift-report-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert aptt_belief_conflicts(text) == []
    assert "78 &mdash; therapeutic" in text or "78 — therapeutic" in text


# --- the remaining corpus guards ------------------------------------------------------------

BANNED = [
    ("pyridoxine-kilogram-scale",
     r"kilogram-scale pyridoxine",
     "pyridoxine for INH toxicity is gram-scale; this page says gram-for-gram eight times",
     "many pharmacies don't stock gram-scale pyridoxine"),
]


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_no_article_carries_the_wrong_statement(label, pattern, why, negative):
    rx = re.compile(pattern, re.I)
    hits = [n for n, t in corpus() if rx.search(t)]
    assert not hits, f"{label}: {why}\n  present in: {', '.join(hits)}"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_can_go_red_on_a_planted_positive(label, pattern, why, negative):
    planted = "many pharmacies don't stock kilogram-scale pyridoxine, so getting enough B6"
    assert re.search(pattern, planted, re.I), f"{label}: detector failed on a planted positive"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_stays_silent_on_the_corrected_wording(label, pattern, why, negative):
    assert not re.search(pattern, negative, re.I), f"{label}: guard fires on corrected text"


def test_the_furosemide_example_now_satisfies_the_rule_the_same_sentence_states():
    """Arithmetic, derived from the page's own multiplier — the Parkland class of repair."""
    with open(os.path.join(REPO, "heart-failure-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = html.unescape(fh.read())
    m = re.search(r"home oral dose\s*[x×]\s*([\d.]+).{0,60}?home\s+(\d+)\s*mg PO daily\s*"
                  r"[^\d]{0,20}give\s+(\d+)\s*mg IV", text, re.S)
    assert m, "the furosemide rule-and-example sentence is no longer recognisable"
    multiplier, home, iv = float(m.group(1)), int(m.group(2)), int(m.group(3))
    assert iv >= home * multiplier, (
        f"the worked example ({home} mg -> {iv} mg IV) still breaks the page's own "
        f"x{multiplier} rule"
    )


def test_the_platelet_row_attributes_the_rise_to_an_apheresis_unit():
    """The Volume cell defines a unit as 50-70 mL, so an unqualified 'per unit' rise reads as a
    single random-donor unit. The qualifier comes verbatim from the dedicated platelet page."""
    with open(os.path.join(REPO, "blood-transfusion-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "per apheresis unit (equivalent to a pool of whole-blood-derived platelets)" in text


def test_the_site_still_publishes_the_platelet_wording_this_repair_propagates():
    hits = [n for n, t in corpus()
            if re.search(r"apheresis unit.{0,80}pool of whole-blood-derived", t, re.S | re.I)]
    assert len(hits) >= 2, f"expected the apheresis qualifier on the source page too, got {hits}"
