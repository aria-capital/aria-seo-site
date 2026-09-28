"""
Tests for fix_contradiction_lane_errors.py, plus the corpus guards that outlive the repair.

Both guards are CORPUS-WIDE rather than file-scoped. The lesson this repo has now paid for
three times — atropine twice, potassium once — is that a defect found in one page was never
searched for in its siblings.

And both prove they can go red: a "must not appear" assertion passes for free when the
detector is broken, the corpus is empty, or the glob is wrong, so each banned pattern is
planted in a synthetic fixture and the same matching logic must fire on it.
"""
import glob
import re
import os

import pytest

import fix_contradiction_lane_errors as F

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
    """Positive control for every scan below. If the glob finds nothing, every 'must not
    appear' assertion in this file passes while measuring exactly zero bytes."""
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


# --- corpus-wide guards --------------------------------------------------------------------

# Patterns, not plain substrings — and that distinction is not cosmetic. The first version of
# this guard banned the literal "50 mg PE/min", which is a SUBSTRING of the correct
# "150 mg PE/min", so it went red on the two pages that state the figure correctly. A guard
# whose needle is a substring of the right answer cries wolf on the healthy corpus.
BANNED = [
    (
        "fosphenytoin-at-phenytoins-ceiling",
        r"(?<![\d.])50\s*mg\s*PE/min",
        "50 mg/min is PHENYTOIN's max rate; fosphenytoin's is 150 mg PE/min, which this site "
        "states three times across two pages and explains as the reason the prodrug exists",
    ),
    (
        "magnesium-toxicity-thresholds-without-units",
        r"Mg &gt;7: respiratory arrest",
        "under the page's own mg/dL label, >7 mg/dL is ~5.8 mEq/L — inside this site's own "
        "published therapeutic band of 4-7 mEq/L for seizure prophylaxis",
    ),
]


@pytest.mark.parametrize("label,pattern,why", BANNED, ids=[b[0] for b in BANNED])
def test_no_article_carries_the_wrong_statement(label, pattern, why):
    rx = re.compile(pattern)
    hits = [name for name, text in corpus() if rx.search(text)]
    assert not hits, f"{label}: {why}\n  present in: {', '.join(hits)}"


@pytest.mark.parametrize("label,pattern,why", BANNED, ids=[b[0] for b in BANNED])
def test_the_guard_can_actually_go_red(label, pattern, why):
    """Plant a real instance of the wrong statement and prove the same logic finds it."""
    planted = {
        "fosphenytoin-at-phenytoins-ceiling":
            "<td>No faster than 50 mg PE/min (fosphenytoin)</td>",
        "magnesium-toxicity-thresholds-without-units":
            "<td>Mg &gt;7: respiratory arrest; Mg &gt;12: cardiac arrest</td>",
    }[label]
    assert re.search(pattern, planted), f"{label}: detector failed on a planted positive"


def test_the_fosphenytoin_guard_does_not_fire_on_the_correct_figure():
    """The negative control the first version of this guard failed. 150 mg PE/min is right,
    and a guard that reddens on it would be trained away within a week."""
    rx = re.compile(BANNED[0][1])
    for correct in ("<td>150 mg PE/min</td>", "Max 150 mg PE/min IV", "at 150 mg PE/min &mdash;"):
        assert not rx.search(correct), f"guard wrongly fires on the correct figure: {correct!r}"


def test_the_site_still_states_fosphenytoins_real_ceiling_somewhere():
    """The repair propagates the site's own figure. If that figure ever disappears from the
    corpus, the correction above has lost its source and someone should look."""
    hits = [n for n, t in corpus() if "150 mg PE/min" in t]
    assert len(hits) >= 2, f"expected the 150 mg PE/min ceiling on at least two pages, got {hits}"


def test_the_phenytoin_clause_in_the_same_cell_was_left_alone():
    """50 mg/min IS phenytoin's ceiling. A repair that rewrote both clauses would have
    replaced one error with another."""
    with open(os.path.join(REPO, "iv-push-medication-safety-icu-nurses-2026.html"),
              encoding="utf-8") as fh:
        text = fh.read()
    assert "50 mg/min (phenytoin)" in text


def test_magnesium_thresholds_now_carry_an_explicit_unit():
    """The harm was unit ambiguity, not just the numbers: the page declares mg/dL above and
    printed mEq/L values below it. Naming the unit inline is what removes the misread."""
    with open(os.path.join(REPO, "fluid-electrolytes-nursing-guide-2026.html"),
              encoding="utf-8") as fh:
        text = fh.read()
    assert "Mg &gt;10 mEq/L: respiratory depression" in text
    assert "Mg &gt;15 mEq/L: cardiac arrest" in text
