"""
Tests for fix_parkland_rate_arithmetic.py, plus the corpus guard that outlives the repair.

The guard here is a different KIND from the other clinical guards in this suite, and that is
the point of the file. Every other one bans a known-wrong string. This one bans a class:
any "V mL over N hr (R mL/hr)" worked example anywhere on the site whose own numbers do not
divide to the rate it prints. It needs no list of drugs and no clinical reference, so it keeps
working on pages nobody has audited and on pages that do not exist yet.

Two properties, both learned expensively in this repo:

  CORPUS-WIDE, not file-scoped. The burns page had never been in any dose inventory; it was
  found by a checker sweeping everything. A defect found in one page was never searched for in
  its siblings - that has cost this repo three atropine rounds and three potassium pages.

  PROVES IT CAN GO RED, and proves it STAYS SILENT. A "must not appear" assertion passes for
  free when the detector is broken, the corpus is empty, or the glob is wrong. And a guard that
  fires on correct content is worse than no guard, because it gets trained away: this repo
  shipped one whose needle ("50 mg PE/min") was a substring of the right answer
  ("150 mg PE/min"), and it reddened the two pages that were correct.

The negative control here is unusually good because it is real content rather than a fixture:
the SAME sentence in the SAME page prints "Next 16 hr: 5,600 mL (350 mL/hr)", which is exactly
right. A checker that cannot tell 700-from-720 apart from 350-from-350 would fail on it.
"""
import glob
import html
import os
import re

import pytest

import fix_parkland_rate_arithmetic as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# "first/next/over N hr: V mL (R mL/hr)"
RATE_EXAMPLE = re.compile(
    r"(?:first|next|over|remaining)\s*(\d+)\s*(?:hr|hours?)[:\s]*([\d,]+)\s*mL\s*\(\s*([\d,]+)\s*mL/hr",
    re.I,
)

_CORPUS = None


def corpus():
    global _CORPUS
    if _CORPUS is None:
        out = []
        for p in sorted(glob.glob(os.path.join(REPO, "*.html"))):
            with open(p, encoding="utf-8", errors="replace") as fh:
                out.append((os.path.basename(p), html.unescape(fh.read())))
        _CORPUS = out
    return _CORPUS


def mismatches(text):
    """Every volume-over-hours example in `text` whose arithmetic does not hold.

    Tolerance is 2% or 1 mL/hr, whichever is larger, so honest rounding in a worked example
    does not read as an error. 5,600/8 = 700 vs a printed 720 is a 2.9% gap and still fails;
    a page printing 701 would not.
    """
    bad = []
    for m in RATE_EXAMPLE.finditer(text):
        hours = int(m.group(1))
        volume = int(m.group(2).replace(",", ""))
        printed = int(m.group(3).replace(",", ""))
        if hours == 0:
            continue
        expected = volume / hours
        if abs(expected - printed) > max(1.0, expected * 0.02):
            bad.append((m.group(0).strip(), round(expected, 1), printed))
    return bad


def test_the_corpus_is_not_empty():
    """Positive control for the scan below."""
    assert len(corpus()) > 1000, "article glob found almost nothing — the guard is blind"


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


def test_the_correction_is_derived_from_the_pages_own_numbers():
    """The property that makes this repair safe without a clinician: the replacement is not a
    borrowed figure or a remembered one, it is what the page's own operands divide to."""
    for path, _old, new, _why, _src in F.EDITS:
        m = RATE_EXAMPLE.search(html.unescape(new))
        assert m, f"{path}: replacement is not a volume-over-hours expression"
        hours, volume, printed = int(m.group(1)), int(m.group(2).replace(",", "")), int(m.group(3).replace(",", ""))
        assert printed == volume / hours, f"{path}: {volume}/{hours} != {printed}"


# --- the guard that outlives the repair ----------------------------------------------------

def test_no_worked_example_on_the_site_contradicts_its_own_arithmetic():
    """Corpus-wide. Fires on any page, audited or not, whose printed rate does not match the
    volume and hours beside it."""
    offenders = []
    for name, text in corpus():
        for expr, expected, printed in mismatches(text):
            offenders.append(f"{name}: {expr!r} prints {printed} mL/hr, arithmetic gives {expected}")
    assert offenders == [], "worked examples contradict their own numbers:\n  " + "\n  ".join(offenders)


def test_the_guard_can_go_red_on_a_planted_positive():
    """Plant the exact error that was live and prove the same logic finds it."""
    planted = "Total = 4 &times; 70 &times; 40 = 11,200 mL<br>First 8 hr: 5,600 mL (720 mL/hr)<br>"
    assert mismatches(html.unescape(planted)), "detector failed on the error it was written for"


def test_the_guard_stays_silent_on_the_correct_line_in_the_same_example():
    """The negative control, and it is real content rather than a fixture: the next line of the
    very same worked example is arithmetically correct and must not fire."""
    assert mismatches("Next 16 hr: 5,600 mL (350 mL/hr)") == []


@pytest.mark.parametrize("correct", [
    "First 8 hr: 5,600 mL (700 mL/hr)",       # the repaired line
    "Next 16 hr: 5,600 mL (350 mL/hr)",       # its sibling
    "First 8 hr: 2,000 mL (250 mL/hr)",
    "over 24 hr: 2,400 mL (100 mL/hr)",
    "First 8 hr: 5,600 mL (701 mL/hr)",       # honest rounding, inside tolerance
])
def test_the_guard_does_not_cry_wolf_on_correct_arithmetic(correct):
    assert mismatches(correct) == [], f"guard wrongly fires on correct arithmetic: {correct!r}"


@pytest.mark.parametrize("wrong", [
    "First 8 hr: 5,600 mL (720 mL/hr)",
    "Next 16 hr: 5,600 mL (400 mL/hr)",
    "First 8 hr: 4,000 mL (250 mL/hr)",
])
def test_the_guard_catches_a_range_of_wrong_rates(wrong):
    assert mismatches(wrong), f"guard missed a genuinely wrong rate: {wrong!r}"


def test_the_burns_example_is_now_internally_consistent_end_to_end():
    """Not just the one number: the whole worked example should survive re-derivation, because
    a reader checking their arithmetic against it checks every line."""
    with open(os.path.join(REPO, "burns-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = html.unescape(fh.read())
    assert "4 × 70 × 40 = 11,200 mL" in text          # 4 mL/kg/%TBSA x 70 kg x 40% TBSA
    assert "First 8 hr: 5,600 mL (700 mL/hr)" in text  # half of 11,200, over 8 h
    assert "Next 16 hr: 5,600 mL (350 mL/hr)" in text  # the other half, over 16 h
    assert mismatches(text) == []
