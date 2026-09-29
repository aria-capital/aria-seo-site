"""
Tests for fix_sweep3_outlier_findings.py, plus the corpus guards that outlive the repair.

The theme of this file is DEPENDENTS. Two repairs earlier the same day fixed a value correctly
and left other claims on the same page resting on the old one, so the page contradicted itself.
Several tests here therefore check whole-page coherence rather than the one string that was
edited — a test asserting only "the table cell now says 0.03-0.04" would have passed while the
prose two paragraphs up still said 0.03-0.06.
"""
import glob
import html
import os
import re

import pytest

import fix_sweep3_outlier_findings as F

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
    assert len(corpus()) > 1000, "article glob found almost nothing — the guards are blind"


def test_every_edit_names_a_real_file():
    for path, _old, _new, _n, _why, _src in F.EDITS:
        assert os.path.exists(os.path.join(REPO, path)), f"{path} does not exist"


def test_the_repair_is_idempotent_against_the_live_tree():
    for path, old, _new, _n, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert fh.read().count(old) == 0, f"{path}: pre-repair text is still present"


def test_every_replacement_landed_the_expected_number_of_times():
    """Not just 'present' — present the number of times the author declared. This is the
    assertion that would have caught a partial edit."""
    for path, _old, new, expected, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            got = fh.read().count(new)
        assert got == expected, f"{path}: corrected wording appears {got}x, expected {expected}x"


def test_no_edit_introduces_a_number_the_site_does_not_already_publish():
    body = "\n".join(t for _n, t in corpus())
    for path, old, new, _n, _why, _src in F.EDITS:
        added = set(re.findall(r"\d+(?:[.,]\d+)?", new)) - set(re.findall(r"\d+(?:[.,]\d+)?", old))
        for num in added:
            assert num in body, f"{path}: {num!r} appears nowhere else on the site"


# --- whole-page coherence, not single-string presence ---------------------------------------

def test_the_vasopressin_page_states_one_routine_dose_throughout():
    """The dependent-check that this repair exists to satisfy. Every routine-dose statement on
    the page must agree; the 0.06 CEILING statements are a separate claim and must survive."""
    with open(os.path.join(REPO, "vasopressor-titration-guide-icu-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "0.03–0.06 units/min" not in text, "a routine-dose statement still prints the ceiling"
    assert text.count("0.03–0.04 units/min") == 3
    # the ceiling is correct and must NOT have been swept up in the replace-all
    assert "Do not exceed 0.06 units/min" in text
    assert "&gt;0.06 units/min (ischemia risk)" in text


def test_the_rocuronium_row_no_longer_contradicts_its_own_succinylcholine_row():
    """The defect was a comparison: rocuronium claimed parity with succinylcholine while
    printing an onset 30 s slower than the succinylcholine row on the same page."""
    with open(os.path.join(REPO, "critical-care-medications-nursing-guide-2026.html"),
              encoding="utf-8") as fh:
        text = html.unescape(fh.read())
    sux = re.search(r"Succinylcholine.{0,300}?fastest onset \((\d+)[–-](\d+) sec\)", text, re.S)
    assert sux, "the succinylcholine onset figure is no longer recognisable"
    roc = re.search(r"Rocuronium.{0,400}?→\s*~?(\d+) sec onset", text, re.S)
    assert roc, "the rocuronium onset figure is no longer recognisable"
    sux_hi, roc_onset = int(sux.group(2)), int(roc.group(1))
    assert roc_onset <= sux_hi, (
        f"rocuronium claims parity with succinylcholine but prints {roc_onset}s against "
        f"succinylcholine's {sux.group(1)}-{sux_hi}s"
    )


def test_the_icp_page_no_longer_calls_a_treatment_threshold_normal():
    with open(os.path.join(REPO, "neurological-assessment-nursing-guide-2026.html"),
              encoding="utf-8") as fh:
        text = html.unescape(fh.read())
    assert "Normal ICP: 5–15 mmHg" in text
    assert "7–20 in some sources" not in text
    # the real threshold statement must survive the deletion
    assert re.search(r"[Ss]ustained ICP\s*&?g?t?;?>?\s*20", html.unescape(text)) or ">20 mmHg" in text


# --- corpus-wide guards ---------------------------------------------------------------------

# (label, regex, why it is wrong, a string the guard must NOT fire on)
BANNED = [
    ("vasopressin-ceiling-as-routine-dose",
     r"0\.03[–-]0\.06 units/min",
     "0.06 units/min is this site's stated ceiling, not a routine dose; fixed is 0.03-0.04",
     "Fixed at 0.03 to 0.04 units/min (not weight-based; not titrated)"),

    ("lactate-clearance-per-hour",
     r"1０?0% or greater decrease per hour|clearance\s*(?:&gt;|>)?=?\s*10%\s*per hour",
     "the site sets lactate clearance at >=10% per 2 hr on two advertised pages",
     "lactate clearance &gt;=10% per 2 hr"),

    ("magnesium-dose-per-gram-of-deficit",
     r"per gram of deficit",
     "a magnesium deficit is never expressed in grams; the denominator does not exist",
     "1&ndash;2 g IV per dose depending on the level and renal function"),

    ("kcl-floor-stock-threshold-excludes-the-hazard",
     r"KCl &gt;2 mEq/mL",
     "the banned concentrate IS 2 mEq/mL; a '>2' threshold excludes what the rule exists for",
     "KCl &gt;1 mEq/mL"),
]


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_no_article_carries_the_wrong_statement(label, pattern, why, negative):
    rx = re.compile(pattern)
    hits = [n for n, t in corpus() if rx.search(t)]
    assert not hits, f"{label}: {why}\n  present in: {', '.join(hits)}"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_can_go_red_on_a_planted_positive(label, pattern, why, negative):
    planted = {
        "vasopressin-ceiling-as-routine-dose":
            "<td>0.03–0.06 units/min (fixed)</td>",
        "lactate-clearance-per-hour":
            "A 10% or greater decrease per hour is a positive indicator of adequate resuscitation.",
        "magnesium-dose-per-gram-of-deficit":
            "typically <strong>1&ndash;2 grams per gram of deficit given over an hour</strong>",
        "kcl-floor-stock-threshold-excludes-the-hazard":
            "<td>KCl &gt;2 mEq/mL, hypertonic saline (3% NaCl), calcium chloride</td>",
    }[label]
    assert re.search(pattern, planted), f"{label}: detector failed on a planted positive"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_stays_silent_on_the_corrected_wording(label, pattern, why, negative):
    """Crying-wolf control. The vasopressin one matters most: its needle must not match the
    page's CORRECT ceiling statements, which legitimately contain 0.06."""
    assert not re.search(pattern, negative), f"{label}: guard fires on corrected text {negative!r}"


def test_the_vasopressin_guard_does_not_fire_on_the_legitimate_ceiling():
    """Explicit control for the substring trap this repo has already been bitten by: 0.06 is a
    real, correct figure on this page in two other roles."""
    rx = re.compile(BANNED[0][1])
    for correct in ("Do not exceed 0.06 units/min without strong justification",
                    "<td>&gt;0.06 units/min (ischemia risk)</td>"):
        assert not rx.search(correct), f"guard wrongly fires on {correct!r}"


def _dash_agnostic(s):
    """This corpus writes en-dashes BOTH ways and the choice is per-page, not per-meaning:
    sepsis-nursing-guide uses `&ndash;` where vasopressor-guide uses a literal `–`. The first
    version of the provenance check below asserted on one encoding and reported 0 hits for a
    phrase that is on two pages — an instrument failure, not a missing source. Normalise."""
    return s.replace("&ndash;", "–").replace("&mdash;", "—").replace("-", "–")


def test_the_site_still_publishes_the_wordings_these_repairs_propagate_from():
    """Provenance. If a source phrasing vanishes, the correction has lost its basis."""
    checks = {
        "0.03-0.04 units/min": 2,          # sepsis + refractory-shock siblings
        "per 2 hr": 2,                     # lactate clearance siblings
        "Normal ICP: 5-15 mmHg": 2,        # TBI sibling + the repaired page
    }
    normalised = [(n, _dash_agnostic(t)) for n, t in corpus()]
    for needle, minimum in checks.items():
        hits = [n for n, t in normalised if _dash_agnostic(needle) in t]
        assert len(hits) >= minimum, f"expected >={minimum} pages carrying {needle!r}, got {len(hits)}"
