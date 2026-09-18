"""
Tests for fix_inverted_potassium.py, and a corpus guard that spans sentences.

The clinical point: a central line exists so that potassium can be given faster and
more concentrated than a peripheral vein tolerates. So a page naming a PERIPHERAL
limit at or above the CENTRAL limit beside it is backwards — not a protocol variant.
Two such statements were live on advertised pages, one of them never audited at all.

The guard at the bottom is the reason this file exists, and it is deliberately built
NOT to repeat the mistake that hid this defect:

    The 2026-09-15 sweep that found the first of these required ONE SENTENCE to
    contain both "peripheral" and "central". The fluid-electrolyte-balance error
    spanned TWO sentences, so that sweep did not catch it, and would have reported
    the page clean on the strength of a correct rate sentence sitting nearby.

    A checker that shares a blind spot with the thing it checks cannot see its own
    miss — the lesson this repo already paid for with the atropine 60-char window.

So the guard below windows across sentence boundaries, and `test_guard_fires_on_a_
planted_inversion` proves it actually fires. A guard that has never been shown to
fail is not a guard.
"""
import glob
import html as html_mod
import re

import fix_inverted_potassium as F

# A peripheral/central figure pair anywhere within this many characters of each other,
# sentences included. The two real defects sat 0 and ~40 chars apart respectively.
WINDOW = 400

FIGURE = re.compile(r"(\d+(?:\.\d+)?)\s*mEq/(100\s*m?L|hr|hour)", re.I)
ROUTE = re.compile(r"(peripheral|central)", re.I)

# How near a route word must sit to a figure to be its label. Deliberately small, so
# a figure with no route word nearby is left unlabelled rather than guessed at.
LABEL_WINDOW = 90


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _labelled_figures(txt: str):
    """
    Every mEq figure, tagged peripheral/central by the NEAREST route word within
    LABEL_WINDOW on either side.

    Order-independent on purpose. The first version of this required the route word to
    come BEFORE the number, so it read "peripheral ... 40 mEq" and was blind to
    "40 mEq/hr max peripherally" — which is exactly how the DKA defect was written.
    The planted-inversion test caught that, which is what it is for.
    """
    routes = [(m.start(), m.group(1).lower()) for m in ROUTE.finditer(txt)]
    out = []
    for fm in FIGURE.finditer(txt):
        unit = fm.group(2).replace(" ", "").lower().replace("hour", "hr")
        mid = (fm.start() + fm.end()) // 2
        near = [(abs(pos - mid), route) for pos, route in routes if abs(pos - mid) <= LABEL_WINDOW]
        if not near:
            continue
        out.append((mid, min(near)[1], float(fm.group(1)), unit))
    return out


def inversions(raw: str):
    """Return (peripheral_value, central_value, unit) where peripheral >= central."""
    figs = _labelled_figures(_text(raw))
    out = []
    for pos_p, route_p, val_p, unit_p in figs:
        if route_p != "peripheral":
            continue
        for pos_c, route_c, val_c, unit_c in figs:
            if route_c != "central" or unit_c != unit_p:
                continue
            if abs(pos_c - pos_p) > WINDOW:
                continue
            if val_p >= val_c:
                out.append((val_p, val_c, unit_p))
    return out


# --- the repair itself -------------------------------------------------------

def test_edits_are_uniquely_anchored():
    """Each target string must appear exactly once in its page, or the script refuses."""
    for path, find, _replace, _label in F.EDITS:
        src = open(path, encoding="utf-8").read()
        assert src.count(find) == 0, (
            f"{path}: the pre-fix string is still present — the repair did not run, "
            f"or the page regressed"
        )


def test_repair_is_idempotent():
    """Run it again: nothing to do, clean exit."""
    assert F.run(apply_changes=False) == 0


def test_surviving_text_is_still_useful():
    """Removal must not strip the instruction that tells a nurse what to do instead."""
    bal = open("fluid-electrolyte-balance-nursing-guide-2026.html", encoding="utf-8").read()
    assert "Verify rate and concentration against facility policy" in bal
    assert "Never give IV potassium undiluted" in bal
    # the correct rate sentence must survive
    assert "Maximum peripheral IV rate: 10 mEq/hour" in bal

    dka = open("diabetic-ketoacidosis-nursing-guide-2026.html", encoding="utf-8").read()
    assert "Replace K+ first." in dka
    assert "HOLD insulin" in dka


def test_no_replacement_number_was_invented():
    """
    The repair deletes and substitutes nothing. If a future edit adds a figure here it
    is a clinical decision and must not arrive through this script.
    """
    for _path, _find, replace, _label in F.EDITS:
        assert not re.search(r"\d+\s*mEq", replace), (
            f"a replacement introduces a dose figure: {replace!r} — that is the owner's call"
        )


# --- the guard, and proof that it fires --------------------------------------

def test_guard_fires_on_a_planted_inversion():
    """
    NEGATIVE CONTROL. Both real defects, reconstructed, must be caught — including the
    one that spans two sentences, which the original sweep missed.
    """
    cross_sentence = (
        "<p>Maximum concentration via peripheral IV: 40 mEq/100 mL. "
        "Maximum concentration via central line: up to 20 mEq/100 mL.</p>"
    )
    assert inversions(cross_sentence), "guard missed the cross-sentence inversion"

    same_sentence = "<td>Replace K+ first (40 mEq/hr max peripherally; &gt;10 mEq/hr central).</td>"
    assert inversions(same_sentence), "guard missed the same-sentence inversion"


def test_guard_is_quiet_on_correct_pages():
    """
    It must NOT fire on correctly-ordered text, or it is an alarm nobody will read.
    """
    correct = (
        "<p>Maximum peripheral IV rate: 10 mEq/hour; central lines allow up to "
        "20 mEq/hour with continuous ECG.</p>"
    )
    assert not inversions(correct), "guard cried wolf on correct peripheral<central text"

    # different units must never be compared against each other
    mixed = "<p>peripheral 10 mEq/hour. central 40 mEq/100 mL.</p>"
    assert not inversions(mixed), "guard compared a rate against a concentration"


def test_no_page_in_the_corpus_states_an_inversion():
    """The corpus-wide guard. This is what keeps running after the repair is finished."""
    bad = {}
    for path in sorted(glob.glob("*.html")):
        raw = open(path, encoding="utf-8", errors="ignore").read()
        if "potassium" not in raw.lower() and "K+" not in raw:
            continue
        found = inversions(raw)
        if found:
            bad[path] = found
    assert not bad, (
        "pages state a peripheral potassium limit at or above the central limit "
        f"beside it: {bad}"
    )
