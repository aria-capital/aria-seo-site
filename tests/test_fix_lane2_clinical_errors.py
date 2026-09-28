"""
Tests for fix_lane2_clinical_errors.py, plus the corpus guards that outlive the repair.

Two properties every guard in this file has, both learned expensively in this repo:

  CORPUS-WIDE, not file-scoped. A defect found in one page was never searched for in its
  siblings — that has now cost this repo three atropine rounds and three potassium pages.

  PROVES IT CAN GO RED. A "must not appear" assertion passes for free when the detector is
  broken, the corpus is empty, or the glob is wrong. Each banned pattern is planted in a
  fixture and the same matching logic must fire on it.

And one property added after the last round failed it: every banned pattern also gets a
NEGATIVE control. The previous guard's needle ("50 mg PE/min") was a substring of the correct
answer ("150 mg PE/min"), so it went red on the two pages that were right. A guard that cries
wolf on the healthy corpus is trained away within a week.
"""
import glob
import os
import re

import pytest

import fix_lane2_clinical_errors as F

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


def test_deletions_introduce_no_new_number():
    """A 'REMOVE' edit must not quietly smuggle in a new clinical number.

    The first version of this test asserted the replacement had to be SHORTER than the
    original, which is not the property that matters and went red on a correct edit: dropping
    ">40-60 mg lorazepam in 1 hour" in favour of "escalating hourly lorazepam dosing" removes
    the false figure while being two characters longer. Length was a proxy; the real invariant
    is that no digit appears in the replacement that was not already in the original."""
    for path, old, new, _why, src in F.EDITS:
        if not src.startswith("deletion"):
            continue
        added = set(re.findall(r"\d+(?:\.\d+)?", new)) - set(re.findall(r"\d+(?:\.\d+)?", old))
        assert not added, f"{path}: deletion introduced new number(s) {sorted(added)}"


def test_propagated_edits_take_their_numbers_from_the_site():
    """Every non-deletion edit either keeps the original's numbers or borrows ones this site
    already publishes. Any digit new to the replacement must appear elsewhere in the corpus."""
    body = "\n".join(t for _n, t in corpus())
    for path, old, new, _why, src in F.EDITS:
        if src.startswith("deletion"):
            continue
        for num in set(re.findall(r"\d+(?:\.\d+)?", new)) - set(re.findall(r"\d+(?:\.\d+)?", old)):
            assert num in body, f"{path}: {num!r} appears nowhere else on the site"


# --- corpus-wide guards --------------------------------------------------------------------

# (label, regex, why it is wrong, a string the guard must NOT fire on)
BANNED = [
    ("citrate-toxicity-called-alkalosis",
     r"Ca:iCa ratio [^<]{0,40}metabolic alkalosis",
     "citrate ACCUMULATION produces a rising-anion-gap metabolic ACIDOSIS, not alkalosis",
     "ratio &gt;2.5; high anion gap metabolic acidosis"),

    ("amiodarone-every-cycle",
     r"amiodarone every cycle",
     "amiodarone in arrest is two doses total (300 mg then 150 mg), never once per cycle",
     "amiodarone 300 mg IV/IO push, then 150 mg for a second dose"),

    ("lorazepam-four-hour-half-life",
     r"lorazepam[^<]{0,80}4-hr half-life|4-hr half-life[^<]{0,60}diazepam",
     "no published lorazepam half-life is 4 h (elimination is ~12-14 h)",
     "First-line for acute SE; respiratory depression"),

    ("diazepam-threshold-attributed-to-lorazepam",
     r"4[05]\s*[-–]\s*60 mg lorazepam in 1 hour",
     "a 40-60 mg first-hour requirement is the DIAZEPAM-equivalent resistance definition",
     "escalating hourly lorazepam dosing"),

    ("inr-comparator-backwards",
     r"INR &gt;1\.5 before invasive procedures",
     "1.5 is a ceiling to stay under before a procedure, not a target to reach",
     "INR must be &lt;1.5 before invasive procedures"),

    ("vancomycin-rate-two-nonequivalent-figures",
     r"1 gram per hour</strong> \(or 10 mg/min\)",
     "1 g/hr is 16.7 mg/min, not 10 — the two figures were presented as equivalents",
     "no faster than <strong>1 gram per hour</strong> to prevent"),

    ("insulin-units-abbreviated-u",
     r"insulin \d+u\b",
     "'u' is the ISMP error-prone abbreviation that reads as 0 or 4",
     "Regular insulin 10 units IV"),
]


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_no_article_carries_the_wrong_statement(label, pattern, why, negative):
    rx = re.compile(pattern)
    hits = [name for name, text in corpus() if rx.search(text)]
    assert not hits, f"{label}: {why}\n  present in: {', '.join(hits)}"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_can_go_red_on_a_planted_positive(label, pattern, why, negative):
    planted = {
        "citrate-toxicity-called-alkalosis":
            "Ca:iCa ratio &gt;2.5, metabolic alkalosis, increasing anion gap",
        "amiodarone-every-cycle": "epinephrine + amiodarone every cycle; treat causes",
        "lorazepam-four-hour-half-life": "Lorazepam: first-line; 4-hr half-life (shorter than diazepam)",
        "diazepam-threshold-attributed-to-lorazepam": "requires &gt;40–60 mg lorazepam in 1 hour without",
        "inr-comparator-backwards": "Warfarin target 2-3. INR &gt;1.5 before invasive procedures",
        "vancomycin-rate-two-nonequivalent-figures":
            "no faster than <strong>1 gram per hour</strong> (or 10 mg/min) to prevent",
        "insulin-units-abbreviated-u": "<td>Regular insulin 10u IV + D50W 50 mL</td>",
    }[label]
    assert re.search(pattern, planted), f"{label}: detector failed on a planted positive"


@pytest.mark.parametrize("label,pattern,why,negative", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_stays_silent_on_the_corrected_wording(label, pattern, why, negative):
    """The control the previous round's guard failed: a needle that also matches the right
    answer is worse than no needle."""
    assert not re.search(pattern, negative), (
        f"{label}: guard wrongly fires on the CORRECTED text {negative!r}"
    )


# --- a few invariants worth keeping beyond the string match --------------------------------

def test_the_site_still_publishes_the_sources_these_repairs_propagate_from():
    """Every PROPAGATE edit borrows wording from a named sibling. If those sources ever vanish,
    the corrections above have lost their provenance and someone should look."""
    checks = {
        "high anion gap metabolic acidosis": 2,   # crrt siblings
        "300 mg": 4,                              # arrest amiodarone
        "4–6 g": 2,                          # eclampsia magnesium load
        "1.7–2.2 mg/dL": 1,                  # magnesium in mg/dL
    }
    for needle, minimum in checks.items():
        hits = [n for n, t in corpus() if needle in t]
        assert len(hits) >= minimum, f"expected >={minimum} pages carrying {needle!r}, got {len(hits)}"


def test_the_eclampsia_row_now_distinguishes_the_two_regimens():
    with open(os.path.join(REPO, "cardiac-dysrhythmia-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "eclampsia is a 4&ndash;6 g IV load" in text


def test_the_magnesium_section_is_now_internally_consistent_in_mEq_L():
    """The page's own column headers are '<1.5' and '>2.5'. Relabelling the heading to mEq/L
    keeps them correct; changing the digits instead would have broken them."""
    with open(os.path.join(REPO, "fluid-electrolytes-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "Magnesium (Normal: 1.5&ndash;2.5 mEq/L)" in text
    assert "Hypomagnesemia (&lt;1.5)" in text and "Hypermagnesemia (&gt;2.5)" in text
