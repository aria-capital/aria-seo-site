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


def test_catches_the_table_layout_that_escaped_the_first_run():
    """The regression that proves the guard and the repair shared a blind spot.

    In cardiac-dysrhythmia-nursing-guide-2026 the drug name, the indication and the dose sit
    in three separate cells, putting ~62 characters between "Atropine" and the figure. The
    original 60-char bound missed it, and because this test file reuses the same regex, the
    corpus guard below reported clean while the wrong dose was still live. A checker that
    shares its blind spot with the thing it checks cannot see its own miss."""
    row = ("<tr><td>Atropine</td><td>Symptomatic bradycardia, heart block (type I/II)</td>"
           "<td>0.5 mg IV q3&ndash;5 min; max 3 mg total</td></tr>")
    out, n = F.correct(row)
    assert n == 1, "the three-cell table layout must be caught"
    assert "<td>1 mg IV q3&ndash;5 min" in out


def test_the_bound_still_refuses_to_cross_into_another_drugs_row():
    """Widening to 120 must not let the pattern reach a different drug's dose. The filler here
    is longer than the bound, so a match would mean the window had stopped being a guard."""
    html = "<td>Atropine</td><td>bradycardia</td>" + ("<td>filler</td>" * 12) + "<td>0.5 mg</td>"
    _out, n = F.correct(html)
    assert n == 0


# --- the RANGE blind spot: the same lesson, a third time -----------------------------------

RANGE_ROW = ("<tr><td>Atropine</td><td>0.5–1 mg</td><td>Rapid IV push</td>"
             "<td>Heart rate response within 1&ndash;2 min</td></tr>"
             "<tr><td>Calcium gluconate</td><td>1&ndash;2 g</td><td>Slow</td>"
             "<td>BP, ECG &mdash; bradycardia</td></tr>")


def test_catches_the_range_form_that_escaped_the_second_run():
    """Found live on iv-push-medication-safety-icu-nurses-2026 on 2026-09-28.

    The guard matched a BARE `0.5 mg` and nothing else, so `0.5-1 mg` walked straight past it
    and the corpus check reported clean for weeks. The table header reads "Typical IV Push
    Dose" and the monitoring cell reads "Heart rate response within 1-2 min", so the indication
    is unambiguously bradycardia, where five other pages on this site all say 1 mg.

    This is the third recurrence of one defect, and each time the guard could not see its own
    miss because it shared a blind spot with the repair. First the 60-char bound, then this."""
    out, n = F.correct(RANGE_ROW)
    assert n == 1, "the range form `0.5-1 mg` must be caught"
    assert "<td>1 mg</td>" in out
    assert "0.5–1 mg" not in out


def test_the_shipped_pattern_really_was_blind_to_the_range():
    """Crying-wolf control, inverted: prove the OLD pattern missed it, so this test file is
    demonstrating a real repair rather than asserting something that was always true."""
    import re
    old = re.compile(r"(?is)(atropine\b.{0,120}?)(\b0\.5\s*mg\b)")
    assert old.search(RANGE_ROW) is None, "the old pattern should NOT match the range form"
    assert F.DOSE.search(RANGE_ROW) is not None, "the widened pattern must match it"
    # and the widened pattern must still catch what the old one caught
    bare = "<td>Atropine</td><td>bradycardia</td><td>0.5 mg</td>"
    assert old.search(bare) is not None and F.DOSE.search(bare) is not None


def test_range_variants_are_all_caught():
    for form in ("0.5–1 mg", "0.5-1 mg", "0.5 to 1 mg", "0.5—1 mg"):
        html = f"<td>Atropine</td><td>symptomatic bradycardia</td><td>{form}</td>"
        _out, n = F.correct(html)
        assert n == 1, f"{form!r} must be caught"


def test_widening_did_not_start_matching_a_correct_one_mg_dose():
    """The obvious way to break this: a pattern loose enough to rewrite an already-correct row."""
    html = "<td>Atropine</td><td>symptomatic bradycardia</td><td>1 mg IV q3&ndash;5 min</td>"
    out, n = F.correct(html)
    assert n == 0 and out == html


def test_no_article_carries_the_range_form_in_a_bradycardia_context():
    """Corpus-wide, not file-scoped — the sibling lesson. A defect found in one page was never
    searched for in its siblings, twice."""
    import glob
    import os
    import re
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rng = re.compile(r"(?is)atropine\b.{0,120}?\b0\.5\s*(?:[-–—]|\s+to\s+)\s*1\s*mg\b")
    offenders = []
    for path in sorted(glob.glob(os.path.join(repo, "*.html"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        for m in rng.finditer(html):
            near = html[max(0, m.start() - F.WINDOW):m.end() + F.WINDOW]
            if F.CONTEXT.search(near):
                offenders.append(os.path.basename(path))
                break
    assert offenders == [], f"atropine 0.5-1 mg live in a bradycardia context: {offenders}"
