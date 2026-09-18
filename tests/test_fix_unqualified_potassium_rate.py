"""
Tests for fix_unqualified_potassium_rate.py, plus a ceiling guard that outlives the repair.

WHY A SECOND POTASSIUM GUARD EXISTS

`tests/test_fix_inverted_potassium.py` already guards this drug. It asks: is a PERIPHERAL figure
stated at or above the CENTRAL figure beside it? That catches a route pair that is backwards, and
it caught two real defects.

It cannot catch a rate with no route at all. Its labeller requires a route word within 90
characters of the number, and deliberately leaves an unlabelled figure alone rather than guessing.
So this, live on an advertised page, read as clean:

    K+ <3.3 mEq/L: HOLD insulin; replace potassium aggressively (20-40 mEq/hr IV) until K+ >=3.5

`test_the_route_based_guard_cannot_see_an_unqualified_rate` below pins that fact by running the
other guard's own labeller against the historical text and asserting it finds nothing. If someone
later widens that guard to cover this case, that test fails and tells them this file is redundant —
which is the useful direction for a test about a blind spot to fail in.

This is the repo's recurring lesson in its third costume. The atropine repair bounded the drug-name
to dose gap at 60 characters and its guard reused the same regex, so the guard went green while a
wrong dose was live. The inverted-potassium sweep required one SENTENCE to hold both route words,
so a two-sentence inversion read clean. Each time the instrument shared a blind spot with the thing
it measured. A green check means what it measures and not one thing more.

THE CEILING WAS MEASURED, NOT CHOSEN
Sweeping every potassium mEq/hr figure in the corpus at the time of writing: twelve figures, eleven
at 10 or 20, and exactly one at 40 — the defect. So a ceiling of 20 flags the real defect with zero
false positives against the healthy corpus. That is the repo's standing method: measure the rule
against the files that are already right, where the correct answer is known, before trusting it on
the ones that are wrong.
"""
import glob
import html as html_mod
import re

import fix_unqualified_potassium_rate as F

LIVE_DEFECT = (
    "<li>K+ &lt;3.3 mEq/L: <strong>HOLD insulin</strong>; replace potassium aggressively "
    "(20–40 mEq/hr IV) until K+ ≥3.5, THEN start insulin</li>"
)

# --- the repair ----------------------------------------------------------------------

def test_removes_the_unqualified_rate():
    out, n = F.correct(LIVE_DEFECT)
    assert n == 1
    assert "mEq/hr" not in out
    assert "aggressively" not in out


def test_keeps_the_clinical_instruction_intact():
    """The bullet exists to order hold -> replete -> start. All three must survive."""
    out, _ = F.correct(LIVE_DEFECT)
    assert "HOLD insulin" in out
    assert "replace potassium until K+ ≥3.5" in out
    assert "THEN start insulin" in out
    assert out.startswith("<li>") and out.endswith("</li>")


def test_leaves_the_concentration_bullet_alone():
    """The next bullet's '20-40 mEq per liter' is a CONCENTRATION and is correct. Removing it
    would replace one error with another — and it is the likely source of the bad rate."""
    sibling = "<li>K+ 3.3–5.0: start insulin; add K+ to IV fluids (20–40 mEq per liter)</li>"
    out, n = F.correct(sibling)
    assert n == 0 and out == sibling


def test_is_idempotent():
    once, n1 = F.correct(LIVE_DEFECT)
    twice, n2 = F.correct(once)
    assert n1 == 1 and n2 == 0 and twice == once


def test_anchor_is_byte_exact_about_the_non_ascii():
    """The live line carries U+2013 and a literal U+2265. An ASCII-spelled anchor matches nothing
    and a naive script would report success having changed nothing."""
    assert "–" in F.FIND and "≥" in F.FIND
    ascii_spelling = LIVE_DEFECT.replace("–", "-").replace("≥", "&ge;")
    _out, n = F.correct(ascii_spelling)
    assert n == 0, "the ASCII spelling must NOT match — that is the silent no-op this guards"


# --- the ceiling guard that outlives the repair ---------------------------------------

# House ceiling. Every potassium page in this corpus caps the rate at 10-20 mEq/hr.
CEILING = 20.0
RATE = re.compile(r"(\d+(?:\.\d+)?)\s*mEq\s*/\s*(?:hr|hour)\b", re.I)
POTASSIUM = re.compile(r"(?i)potassium|\bK\+|KCl")
CONTEXT = 200


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
        "potassium infusion rate above the house ceiling of "
        f"{CEILING:g} mEq/hr:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_actually_fires_on_a_planted_violation():
    """A guard that has never been shown to fail is not a guard."""
    planted = _text("<li>replace potassium aggressively (20–40 mEq/hr IV) until K+ ≥3.5</li>")
    assert over_ceiling(planted), "the ceiling guard must fire on the defect it was built for"


def test_the_guard_does_not_fire_on_the_healthy_corpus_wording():
    """The eleven legitimate figures all sit at 10 or 20. None may be flagged."""
    for ok in (
        "Max rate 10–20 mEq/hr peripheral vein (10 mEq/hr standard; 20 mEq/hr only with "
        "continuous cardiac monitoring).",
        "Maximum peripheral IV rate: 10 mEq/hour (faster rates require cardiac monitoring).",
        "Peripheral lines tolerate roughly 10 mEq/hour; higher rates (often up to ~20 mEq/hour) "
        "and concentrations need a central line.",
    ):
        assert over_ceiling(ok) == [], ok


def test_the_guard_ignores_a_concentration():
    """mEq per LITRE is a concentration. 40 mEq/L in a bag is routine; the guard must not
    confuse it with 40 mEq into a vein per hour — that conflation caused the defect."""
    assert over_ceiling("add K+ to IV fluids (20–40 mEq per liter)") == []
    assert over_ceiling("many protocols cap peripheral potassium at 40 mEq/L") == []


def test_the_route_based_guard_cannot_see_an_unqualified_rate():
    """Pins WHY this file exists, and fails usefully if that stops being true.

    The inverted-potassium guard labels a figure peripheral/central by the nearest route word
    within its label window. This sentence has no route word, so that guard leaves the figure
    unlabelled and reports clean. If someone widens it to cover route-free rates, this test fails
    and whoever is reading can retire this file as redundant."""
    import tests.test_fix_inverted_potassium as other

    txt = other._text(LIVE_DEFECT)
    assert other.FIGURE.search(txt), "sanity: the other guard's regex does see the number"
    assert other._labelled_figures(txt) == [], (
        "the route-based guard now labels a route-free rate — it may have been widened to cover "
        "this case, in which case this file's ceiling guard may be redundant. Check before deleting."
    )
