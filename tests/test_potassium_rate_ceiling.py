"""
A ceiling on IV potassium infusion RATES, corpus-wide — the class the route-based guard
cannot see.

WHY A SECOND POTASSIUM GUARD EXISTS

`tests/test_fix_inverted_potassium.py` already guards this drug, and guards it well. It asks:
is a PERIPHERAL figure stated at or above the CENTRAL figure beside it? That catches a route
pair that is backwards, and it caught two real defects.

It cannot catch a rate with no route at all. Its labeller tags a figure peripheral/central by
the nearest route word within 90 characters, and deliberately leaves an unlabelled figure
alone rather than guessing. So this, live on an advertised page, read as clean:

    K+ <3.3 mEq/L: HOLD insulin; replace potassium aggressively (20-40 mEq/hr IV) until K+ >=3.5

40 mEq/hr was double the highest rate this site permits anywhere else. No route word appears
anywhere near it, so the figure was never labelled and the page passed.

`test_the_route_based_guard_cannot_see_an_unqualified_rate` below pins that, by running the
other guard's own labeller against the historical text and asserting it finds nothing. If
someone later widens that guard to cover this case, that test fails and tells them this file
became redundant — the useful direction for a test about a blind spot to fail in.

This is the repo's recurring lesson in its third costume. The atropine repair bounded the
drug-name-to-dose gap at 60 characters and its guard reused the same regex, so the guard went
green while a wrong dose was live. The inverted-potassium sweep required one SENTENCE to hold
both route words, so a two-sentence inversion read clean. Each time the instrument shared a
blind spot with the thing it measured. A green check means what it measures and not one thing
more.

WHERE THE DEFECT CAME FROM, because the generator matters more than the instance
One bullet below the bad rate sat "add K+ to IV fluids (20-40 mEq per LITER)" — a
CONCENTRATION, and unremarkable. The bullet above reprinted those digits as a RATE.
Rate-for-concentration is the generator of this entire family of potassium defects: 40 mEq/L
in a bag is routine, 40 mEq/hr into a vein is not. Hence
`test_the_guard_ignores_a_concentration`: a guard that conflated the two would be reproducing
the very mistake it exists to catch.

THE CEILING WAS MEASURED, NOT CHOSEN
Sweeping every potassium mEq/hr figure in the corpus while the defect was still live: twelve
figures, eleven at 10 or 20, and exactly one at 40 — the defect. So a ceiling of 20 flagged
the real defect with zero false positives against the healthy corpus. That is the repo's
standing method: measure a rule against the files that are already right, where the correct
answer is known, before trusting it on the ones that are wrong.

NOTE ON PROVENANCE
The offending line was removed on `main` in 67b53040 by a concurrent session, which replaced
both bullets with "per facility protocol" wording. This file is deliberately NOT tied to that
repair, or to any script: it is a standing invariant over the corpus, so it keeps working
whoever makes the next edit and whatever wording they choose.
"""
import glob
import html as html_mod
import re

# House ceiling. Every potassium page in this corpus caps the infusion rate at 10-20 mEq/hr.
CEILING = 20.0

RATE = re.compile(r"(\d+(?:\.\d+)?)\s*mEq\s*/\s*(?:hr|hour)\b", re.I)
POTASSIUM = re.compile(r"(?i)potassium|\bK\+|KCl")
CONTEXT = 200

# The exact text that was live on diabetes-dka-hhs-nursing-guide-2026 before 67b53040.
HISTORICAL_DEFECT = (
    "<li>K+ &lt;3.3 mEq/L: <strong>HOLD insulin</strong>; replace potassium aggressively "
    "(20–40 mEq/hr IV) until K+ ≥3.5, THEN start insulin</li>"
)


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", raw)))


def over_ceiling(txt: str):
    """Every potassium infusion rate above the house ceiling. Returns [(value, excerpt)]."""
    out = []
    for m in RATE.finditer(txt):
        near = txt[max(0, m.start() - CONTEXT):m.end() + CONTEXT]
        if not POTASSIUM.search(near):
            continue  # mEq/hr for something that is not potassium
        if float(m.group(1)) > CEILING:
            out.append((float(m.group(1)), txt[max(0, m.start() - 80):m.end() + 40].strip()))
    return out


# --- the invariant -------------------------------------------------------------------

def test_no_live_page_prints_a_potassium_rate_above_the_house_ceiling():
    """Corpus-wide. Route word or not, a potassium rate above 20 mEq/hr does not ship."""
    offenders = []
    for path in sorted(glob.glob("*.html")):
        raw = open(path, encoding="utf-8", errors="replace").read()
        if not POTASSIUM.search(raw):
            continue
        for value, excerpt in over_ceiling(_text(raw)):
            offenders.append(f"{path}: {value:g} mEq/hr — …{excerpt}…")
    assert offenders == [], (
        f"potassium infusion rate above the house ceiling of {CEILING:g} mEq/hr:\n  "
        + "\n  ".join(offenders)
    )


# --- proof the guard is not vacuous --------------------------------------------------

def test_the_guard_fires_on_the_historical_defect():
    """A guard that has never been shown to fail is not a guard. This is the real text that
    was live, so this test would have caught it on the day it was written."""
    found = over_ceiling(_text(HISTORICAL_DEFECT))
    assert found, "the ceiling guard must fire on the defect it was built for"
    assert found[0][0] == 40.0


def test_the_guard_fires_regardless_of_spacing_and_case():
    for variant in ("50 mEq/hr", "50mEq/hour", "50 MEQ / HR"):
        assert over_ceiling(f"potassium replacement at {variant} IV"), variant


def test_the_guard_does_not_fire_on_the_healthy_corpus_wording():
    """The legitimate figures all sit at 10 or 20. None may be flagged — a guard with false
    positives is one people learn to ignore, which is how the truncation bug ran for months."""
    for ok in (
        "Max rate 10–20 mEq/hr peripheral vein (10 mEq/hr standard; 20 mEq/hr only with "
        "continuous cardiac monitoring).",
        "Maximum peripheral IV rate: 10 mEq/hour (faster rates require cardiac monitoring).",
        "Peripheral lines tolerate roughly 10 mEq/hour; higher rates (often up to ~20 mEq/hour) "
        "and concentrations need a central line.",
        "replace PO or IV (max 10–20 mEq/hr IV with cardiac monitoring)",
    ):
        assert over_ceiling(ok) == [], ok


def test_the_guard_ignores_a_concentration():
    """mEq per LITRE is a concentration. 40 mEq/L in a bag is routine; the guard must not
    confuse it with 40 mEq into a vein per hour. Conflating the two is what caused the defect,
    so a guard that repeated the conflation would be worse than none."""
    assert over_ceiling("add K+ to IV fluids (20–40 mEq per liter)") == []
    assert over_ceiling("many protocols cap peripheral potassium at 40 mEq/L") == []
    assert over_ceiling("maximum concentration 40 mEq/100 mL via central line") == []


def test_the_guard_ignores_a_rate_that_is_not_potassium():
    """mEq/hr appears for other electrolytes. Only potassium is in scope here."""
    assert over_ceiling("sodium bicarbonate infusion at 50 mEq/hr for the acidosis") == []


# --- the blind spot this file exists to cover ----------------------------------------

def test_the_route_based_guard_cannot_see_an_unqualified_rate():
    """Pins WHY this file exists, and fails usefully if that stops being true.

    The inverted-potassium guard labels a figure peripheral/central by the nearest route word.
    The historical defect has no route word, so that guard leaves the figure unlabelled and
    reports clean. If someone widens it to cover route-free rates, this test fails and whoever
    is reading can retire this file as redundant."""
    import tests.test_fix_inverted_potassium as other

    txt = other._text(HISTORICAL_DEFECT)
    assert other.FIGURE.search(txt), "sanity: the other guard's regex does see the number"
    assert other._labelled_figures(txt) == [], (
        "the route-based guard now labels a route-free rate — it may have been widened to "
        "cover this case, in which case this ceiling guard may be redundant. Check before "
        "deleting either."
    )
