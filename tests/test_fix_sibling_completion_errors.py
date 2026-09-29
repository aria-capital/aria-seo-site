"""
Tests for fix_sibling_completion_errors.py, plus the corpus guards that outlive the repair.

Every guard here is CORPUS-WIDE, proves it can go RED on a planted positive, and proves it
stays SILENT on the corrected wording. That third property is not decoration: this repo shipped
a guard whose needle ("50 mg PE/min") was a substring of the right answer ("150 mg PE/min"), so
it reddened the two pages that were correct. A guard that cries wolf on healthy content gets
trained away within a week, which is worse than having no guard at all.

The lidocaine guard is the interesting one, because the defect is an OMISSION. You cannot ban a
missing string. So it is written as a conditional instead: a page that gives lidocaine's arrest
LOADING dose and then says "repeat" must also say what the repeat dose is. That shape survives
rewording, and it generalises to any page added later.
"""
import glob
import os
import re

import pytest

import fix_sibling_completion_errors as F

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
    """The invariant that separates a propagation from an invention. Any digit new to a
    replacement must already appear somewhere in this corpus."""
    body = "\n".join(t for _n, t in corpus())
    for path, old, new, _why, _src in F.EDITS:
        added = set(re.findall(r"\d+(?:\.\d+)?", new)) - set(re.findall(r"\d+(?:\.\d+)?", old))
        for num in added:
            assert num in body, f"{path}: {num!r} appears nowhere else on the site"


# --- lidocaine: guarding an OMISSION --------------------------------------------------------

# A page in arrest context that gives the 1-1.5 mg/kg load and then says "repeat" must say what
# the repeat dose is. Written as a conditional because you cannot ban a string that is absent.
LOAD_THEN_REPEAT = re.compile(
    r"lidocaine.{0,400}?1\s*(?:&ndash;|[-–])\s*1\.5\s*(?:&nbsp;|\s)*mg/kg.{0,120}?repeat",
    re.I | re.S,
)
REPEAT_DOSE = re.compile(r"0\.5\s*(?:&ndash;|[-–])\s*0\.75\s*(?:&nbsp;|\s)*mg/kg", re.I)


def test_no_page_gives_lidocaines_load_then_repeat_without_naming_the_repeat_dose():
    """Corpus-wide. 'Repeat boluses' after a 1-1.5 mg/kg load reads as repeating 1-1.5 mg/kg;
    the repeat is 0.5-0.75 mg/kg, which this site states on two other pages."""
    offenders = []
    for name, text in corpus():
        for m in LOAD_THEN_REPEAT.finditer(text):
            window = text[m.start():m.end() + 260]
            if not REPEAT_DOSE.search(window):
                offenders.append(name)
                break
    assert offenders == [], (
        "lidocaine load-then-repeat with no repeat dose named: " + ", ".join(offenders)
    )


def test_the_lidocaine_guard_can_go_red_on_the_wording_that_was_live():
    planted = ("<strong>Lidocaine</strong> is a reasonable substitute, dosed at "
               "1&ndash;1.5&nbsp;mg/kg with repeat boluses. Both are followed by an infusion.")
    m = LOAD_THEN_REPEAT.search(planted)
    assert m, "detector failed on the exact wording that was live"
    assert not REPEAT_DOSE.search(planted[m.start():m.end() + 260]), "planted text should lack the repeat dose"


def test_the_lidocaine_guard_stays_silent_on_the_corrected_wording():
    """Negative control, using the page's REAL repaired sentence rather than a fragment.

    The first version of this test dropped the word "lidocaine" from its fixture, so the
    pattern — which anchors on the drug name — never matched and the control asserted nothing
    about the guard. A negative control built from a fragment tests the fragment."""
    fixed = ("<strong>Lidocaine</strong> is a reasonable substitute when amiodarone isn't "
             "available or the team prefers it, dosed at 1&ndash;1.5&nbsp;mg/kg, with repeat "
             "boluses of 0.5&ndash;0.75&nbsp;mg/kg. Both are followed by a maintenance infusion.")
    m = LOAD_THEN_REPEAT.search(fixed)
    assert m, "the guard should still MATCH the load-then-repeat shape after the repair"
    assert REPEAT_DOSE.search(fixed[m.start():m.end() + 260]), "and should find the repeat dose, so it stays silent"


def test_the_repaired_page_satisfies_the_guard_non_vacuously():
    """The corpus scan passes either because the page names the repeat dose, or because the
    guard no longer matches the page at all. Those are very different, so pin the first one."""
    with open(os.path.join(REPO, "amiodarone-vs-lidocaine-icu-nurses-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    m = LOAD_THEN_REPEAT.search(text)
    assert m, "the guard must still recognise this page's load-then-repeat sentence"
    assert REPEAT_DOSE.search(text[m.start():m.end() + 260]), "and the repeat dose must be present"


def test_the_site_still_publishes_the_repeat_dose_this_repair_propagates():
    """If the source wording ever disappears, the correction has lost its provenance."""
    hits = [n for n, t in corpus() if REPEAT_DOSE.search(t)]
    assert len(hits) >= 2, f"expected the 0.5-0.75 mg/kg repeat on at least two pages, got {hits}"


# --- DKA: guarding an INTERNAL CONTRADICTION ------------------------------------------------

HOLD_RESUME = re.compile(r"HOLD insulin</strong>.{0,160}?until K\+ ≥(\d\.\d)", re.I | re.S)
START_ROW = re.compile(r"K\+ (\d\.\d)(?:&ndash;|[-–])5\.0: start insulin", re.I)


def test_no_dka_page_holds_insulin_to_a_threshold_its_own_start_row_contradicts():
    """Corpus-wide, and it compares the page against ITSELF rather than against a remembered
    figure. Both 3.3 and 3.5 are published thresholds — the defect is one page printing both."""
    offenders = []
    for name, text in corpus():
        resume = HOLD_RESUME.search(text)
        start = START_ROW.search(text)
        if resume and start and resume.group(1) != start.group(1):
            offenders.append(f"{name}: resumes at {resume.group(1)} but its start row says {start.group(1)}")
    assert offenders == [], "DKA insulin threshold contradicts itself:\n  " + "\n  ".join(offenders)


def test_the_dka_guard_can_go_red_on_the_wording_that_was_live():
    planted = ("<li>K+ &lt;3.3 mEq/L: <strong>HOLD insulin</strong>; replace potassium "
               "aggressively (20–40 mEq/hr IV) until K+ ≥3.5, THEN start insulin</li>"
               "<li>K+ 3.3&ndash;5.0: start insulin; add K+ to IV fluids</li>")
    resume, start = HOLD_RESUME.search(planted), START_ROW.search(planted)
    assert resume and start and resume.group(1) != start.group(1), "detector missed the live contradiction"


def test_the_dka_guard_stays_silent_on_the_corrected_wording():
    fixed = ("<li>K+ &lt;3.3 mEq/L: <strong>HOLD insulin</strong>; replace potassium "
             "aggressively (20–40 mEq/hr IV) until K+ ≥3.3, THEN start insulin</li>"
             "<li>K+ 3.3&ndash;5.0: start insulin; add K+ to IV fluids</li>")
    resume, start = HOLD_RESUME.search(fixed), START_ROW.search(fixed)
    assert resume and start and resume.group(1) == start.group(1)


def test_the_dka_guard_does_not_care_which_published_threshold_a_page_picks():
    """The property that keeps this guard honest: a page consistently using 3.5 must PASS.
    The guard measures self-consistency, not agreement with a number chosen here."""
    consistent_35 = ("<li>K+ &lt;3.5 mEq/L: <strong>HOLD insulin</strong>; replace potassium "
                     "until K+ ≥3.5, THEN start insulin</li>"
                     "<li>K+ 3.5&ndash;5.0: start insulin</li>")
    resume, start = HOLD_RESUME.search(consistent_35), START_ROW.search(consistent_35)
    assert resume and start and resume.group(1) == start.group(1), "a self-consistent page must pass"


def test_the_dka_potassium_rate_is_deferred_to_protocol_not_reprinted():
    """This assertion was inverted mid-flight by a concurrent session, and the history is worth
    keeping because it is the repo's "several sessions land work here on the same day" hazard
    playing out on one sentence.

    It originally read `assert "20-40 mEq/hr IV" in text`, guarding a figure that had SURVIVED an
    adversarial refute pass (20-40 mEq/hr is published for K+ <3.3 in DKA), on the principle that
    re-correcting a verified-correct number ships a new error. While this branch was open, commit
    67b53040 landed on main and removed that rate anyway — replacing it with "per facility
    protocol and the active order".

    That was not a contradiction of the refute pass and the guard is not being weakened to
    accommodate it. The refute pass asked "is 20-40 mEq/hr wrong?" — it is not. The other session
    asked a different question: should a bare hourly potassium rate be printed with no access
    route at all, when the peripheral-vs-central distinction is the thing that makes concentrated
    potassium dangerous and is the defect class this corpus has already been bitten by three
    times. Deleting the number defers to the order rather than choosing between published ranges,
    which is exactly standing priority 5.

    So the invariant worth holding is not "that number is present" but "no unqualified hourly
    potassium rate is printed here", which is strictly stronger than what this test used to say.
    """
    with open(os.path.join(REPO, "diabetes-dka-hhs-nursing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    assert "per facility protocol and the active order" in text
    assert not re.search(r"\d+\s*[-–]\s*\d+\s*mEq/hr", text), (
        "an unqualified hourly potassium rate is back on the DKA page"
    )
