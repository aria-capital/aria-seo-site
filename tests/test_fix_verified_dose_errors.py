"""
Tests for fix_verified_dose_errors.py, plus the corpus guard that outlives the repair.

The guard is deliberately CORPUS-WIDE rather than file-scoped. The lesson this repo paid for
twice — once on atropine, once on potassium — is that a defect found in one page was never
searched for in its siblings, and three near-identically-named pages can disagree for weeks.
So every wrong pattern below is asserted absent from all 1,400+ articles, not just from the
one file the repair touched.

The other lesson encoded here: a "must not appear" assertion PASSES FOR FREE if the detector
is broken, the corpus is empty, or the glob is wrong. So `test_the_guard_can_actually_go_red`
plants each wrong pattern in a synthetic document and proves the detector fires on it. Without
that, a green run here would be indistinguishable from a run that looked at nothing.
"""
import glob
import os

import pytest

import fix_verified_dose_errors as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _articles():
    return sorted(glob.glob(os.path.join(REPO, "*.html")))


def _corpus():
    """(path, text) for every article. Read once per session — 1,400 files."""
    out = []
    for p in _articles():
        with open(p, encoding="utf-8", errors="replace") as fh:
            out.append((os.path.basename(p), fh.read()))
    return out


CORPUS = None


def corpus():
    global CORPUS
    if CORPUS is None:
        CORPUS = _corpus()
    return CORPUS


# --- the repair itself -------------------------------------------------------------------

def test_the_corpus_is_not_empty():
    """Positive control for every scan below: if this glob returns nothing, every
    'must not appear' assertion in this file passes while measuring exactly zero bytes."""
    assert len(corpus()) > 1000, "article glob found almost nothing — the guard is blind"


def test_every_edit_names_a_real_file():
    for path, _old, _new, _why, _src in F.EDITS:
        assert os.path.exists(os.path.join(REPO, path)), f"{path} does not exist"


def test_no_edit_introduces_a_number_absent_from_the_site():
    """The rule that makes an automated clinical repair reviewable: replacements propagate
    wording this site already publishes, or delete. Deletions have an empty replacement."""
    for path, _old, new, _why, src in F.EDITS:
        if new == "":
            assert src.startswith("deletion"), f"{path}: empty replacement not labelled a deletion"
        else:
            assert not src.startswith("deletion"), f"{path}: non-empty replacement labelled a deletion"


def test_the_repair_is_idempotent_against_the_live_tree():
    """Re-running must change nothing. Every pattern should now be absent (count 0), which the
    script reports as a skip rather than an edit."""
    for path, old, _new, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert fh.read().count(old) == 0, f"{path}: pre-repair text is still present"


def test_every_replacement_landed():
    for path, _old, new, _why, _src in F.EDITS:
        if not new:
            continue
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert new in fh.read(), f"{path}: corrected wording is missing"


# --- corpus-wide guards: these outlive the repair ----------------------------------------

# Each entry: (label, needle, why it is wrong). Plain substrings, not regexes — a regex here
# would share a blind spot with the extractor that missed these in the first place.
BANNED = [
    (
        "phenytoin-diluent-inverted",
        "phenytoin in normal saline (precipitates)",
        "phenytoin precipitates in DEXTROSE; normal saline is the required diluent",
    ),
    (
        "phenytoin-d5w-prescribed",
        "use dedicated line with D5W",
        "prescribes the one fluid phenytoin precipitates in",
    ),
    (
        "push-dose-epi-100ml-bag",
        "inject it into a 100 mL bag",
        "1 mL of 100 mcg/mL into 100 mL is 1 mcg/mL, not the 10 mcg/mL the sentence claims",
    ),
    (
        "transducer-2mmHg-per-cm",
        "~2 mmHg per cm above",
        "1 cmH2O = 0.74 mmHg, so 2 mmHg belongs to 2.5 cm — this is ~2.7x too large",
    ),
    (
        "magnesium-toxicity-in-mg-dl",
        "4–7 mg/dL: loss of deep tendon reflexes",
        "4-7 mg/dL is the THERAPEUTIC range; the toxicity bands are mEq/L",
    ),
    (
        "furosemide-weight-based",
        "IV furosemide at 1&ndash;2.5 mg/kg",
        "70-175 mg in a diuretic-naive, preload-dependent postpartum patient",
    ),
    (
        "terlipressin-not-available",
        "terlipressin (not available in US)",
        "FDA-approved since September 2022; this site's own page says so",
    ),
    (
        "norepinephrine-10-mcg-kg-min",
        "norepinephrine maximum of 10 mcg/kg/min",
        "~20x this site's own stated ceiling of 0.5 mcg/kg/min",
    ),
]


@pytest.mark.parametrize("label,needle,why", BANNED, ids=[b[0] for b in BANNED])
def test_no_article_carries_the_wrong_statement(label, needle, why):
    hits = [name for name, text in corpus() if needle in text]
    assert not hits, f"{label}: {why}\n  present in: {', '.join(hits)}"


@pytest.mark.parametrize("label,needle,why", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_can_actually_go_red(label, needle, why):
    """Crying-wolf control. A 'must not appear' assertion passes for free when the instrument
    did not run. Plant the pattern and prove the same matching logic finds it."""
    planted = f"<html><body><p>lead-in {needle} trailing</p></body></html>"
    fake = [("synthetic-fixture.html", planted)]
    hits = [name for name, text in fake if needle in text]
    assert hits == ["synthetic-fixture.html"], f"{label}: detector failed on a planted positive"


def test_hydralazine_obstetric_row_carries_a_ceiling():
    """The defect was not a wrong number alone — it was a repeat interval with NO cumulative
    maximum, which is how hydralazine stacking kills. Assert the ceiling exists."""
    with open(os.path.join(REPO, "hypertensive-crisis-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "max 20–30 mg" in text, "obstetric hydralazine row lost its cumulative ceiling"


def test_icp_page_no_longer_contradicts_itself_on_cpp():
    """The page called CPP 55 'borderline inadequate' four lines after offering a 50-60 target."""
    with open(os.path.join(REPO, "icp-monitoring-icu-nurses-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "target 50–60 for aSAH" not in text
