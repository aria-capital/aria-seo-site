"""
Tests for fix_arrest_amiodarone_dose.py, plus the corpus guard that outlives the repair.

The distinction the guard protects: "150 mg over 10 minutes" is the STABLE VT regimen, and
in cardiac arrest amiodarone is 300 mg IV/IO push (150 mg for the second dose). A page that
prints the perfusing-rhythm regimen against a pulseless indication is telling a nurse to hang
a 10-minute infusion during CPR.
"""
import glob
import re
from pathlib import Path

import fix_arrest_amiodarone_dose as F

CELL = ("<td>Amiodarone</td><td>V-Tach, V-Fib</td><td>150 mg over 10 min for pulseless VT/VF; "
        "150 mg over 10 min for stable VT; monitor QT</td>")


def test_corrects_the_arrest_clause():
    out, n = F.correct(CELL)
    assert n == 1
    assert "300 mg IV/IO push for pulseless VT/VF (150 mg for a second dose)" in out


def test_leaves_the_stable_vt_clause_untouched():
    """The same dose and rate are CORRECT for stable VT and appear in the same cell. A repair
    that also rewrote them would replace one error with another."""
    out, _ = F.correct(CELL)
    assert "150 mg over 10 min for stable VT" in out
    assert out.count("300 mg") == 1


def test_does_not_touch_a_correct_page():
    correct_text = "<p>amiodarone (300mg IV/IO for VF/pulseless VT, 150mg for stable VT)</p>"
    out, n = F.correct(correct_text)
    assert n == 0 and out == correct_text


def test_is_idempotent():
    once, n1 = F.correct(CELL)
    twice, n2 = F.correct(once)
    assert n1 == 1 and n2 == 0 and twice == once


def test_tolerates_spacing_and_case_variants():
    for variant in ("150mg over 10 minutes for pulseless VT/VF",
                    "150 MG OVER 10 MIN FOR PULSELESS VT / VF"):
        _out, n = F.correct(f"<td>{variant}</td>")
        assert n == 1, variant


# --- the guard that outlives the repair ----------------------------------------------

def test_no_live_page_gives_a_perfusing_rhythm_amiodarone_dose_for_arrest():
    """Corpus-wide. If a regenerated article reintroduces the stable-VT regimen against a
    pulseless indication, fail here rather than shipping it to an ICU nurse."""
    offenders = [p for p in sorted(glob.glob("*.html"))
                 if F.ARREST.search(Path(p).read_text(encoding="utf-8", errors="replace"))]
    assert offenders == [], (
        f"amiodarone 150 mg over 10 min printed for pulseless VT/VF in: {offenders}. "
        "Arrest dosing is 300 mg IV/IO push, then 150 mg."
    )
