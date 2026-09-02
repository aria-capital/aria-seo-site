"""
Tests for fix_atropine_dose.py, and a corpus guard against the dose coming back.

The value matters clinically: the 2020 AHA adult bradycardia algorithm raised the first
atropine dose to 1 mg. 0.5 mg is the pre-2020 figure, and it is what the 2026-08-19 clinical
hold pulled a product for. The same figure was still live in five articles eight weeks later
because nobody searched the corpus after finding it once.

The corpus guard at the bottom is the point of this file — the repair script has run and is
finished, but the guard keeps running forever.
"""
import glob
import re
from pathlib import Path

import fix_atropine_dose as F


def test_corrects_a_bradycardia_dose():
    html = "<p>if symptomatic: atropine 0.5 mg IV; prepare for pacing</p>"
    out, n = F.correct(html)
    assert n == 1 and "atropine 1 mg IV" in out


def test_corrects_inside_a_table_row():
    # code-blue's drug table splits the name and the dose across cells, which a
    # naive "atropine 0.5 mg" pattern misses entirely.
    html = "<tr><td>Atropine</td><td>0.5 mg IV (max 3 mg)</td><td>Symptomatic bradycardia</td></tr>"
    out, n = F.correct(html)
    assert n == 1 and "<td>1 mg IV (max 3 mg)</td>" in out


def test_leaves_the_paradoxical_bradycardia_clause_alone():
    """A real sentence from the corpus. The trailing 0.5 mg is CORRECT clinical content —
    sub-0.5 mg doses really can cause paradoxical bradycardia — so only the leading dose
    may change. Getting this wrong would turn a correction into a new error."""
    html = ("<td>Atropine</td><td>Symptomatic bradycardia</td><td>0.5mg IV; may repeat up to "
            "3mg total; paradoxical bradycardia possible with doses below 0.5mg</td>")
    out, n = F.correct(html)
    assert n == 1
    assert "<td>1 mg IV; may repeat" in out
    assert "possible with doses below 0.5mg" in out  # preserved


def test_does_not_touch_a_dose_with_no_bradycardia_context():
    # 0.5 mg is correct for other atropine indications; context is what makes it wrong.
    html = "<p>atropine 0.5 mg IM as an antisialagogue before the procedure</p>"
    out, n = F.correct(html)
    assert n == 0 and out == html


def test_does_not_leap_to_another_drugs_dose():
    html = "<tr><td>Atropine</td></tr><tr><td>Symptomatic bradycardia</td></tr>" + "x" * 200 + "<td>0.5 mg</td>"
    _out, n = F.correct(html)
    assert n == 0


def test_is_idempotent():
    html = "<p>symptomatic bradycardia: atropine 0.5 mg IV</p>"
    once, n1 = F.correct(html)
    twice, n2 = F.correct(once)
    assert n1 == 1 and n2 == 0 and twice == once


# --- the guard that outlives the repair ----------------------------------------------

def test_no_live_page_gives_atropine_0_5_mg_for_bradycardia():
    """Corpus-wide. If a regenerated or newly added article reintroduces the pre-2020 dose,
    fail here rather than shipping it to an ICU nurse."""
    offenders = []
    for path in sorted(glob.glob("*.html")):
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        for m in F.DOSE.finditer(html):
            near = html[max(0, m.start() - F.WINDOW):m.end() + F.WINDOW]
            if F.CONTEXT.search(near):
                offenders.append(path)
                break
    assert offenders == [], (
        "pre-2020 atropine dose (0.5 mg) live in a bradycardia context: "
        f"{offenders}. The 2020 algorithm first dose is 1 mg."
    )
