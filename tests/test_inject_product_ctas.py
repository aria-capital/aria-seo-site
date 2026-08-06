"""
Tests for inject_product_ctas.py.

Three failure modes matter, and they are not equally bad. Stacking a second offer onto
an article on the next run is the one that hits 555 files at once (repo rule 3). Pointing
a buy button at a permalink that is not on the store is the one a reader actually feels.
And offering an ICU pocket card on a retirement-planning article is the one that makes the
whole site look automated — so "no match" must stay a real, common outcome, not a fallback
that quietly catches everything.

The corpus-level tests at the bottom are the ones that guard the invariants going forward.
"""
import glob
import re

import inject_product_ctas as I

# The nine permalinks live on icunotebook.gumroad.com, measured logged-out 2026-08-05.
LIVE = {"avsrc", "bvezxw", "dpdvwf", "itikqo", "kvppg", "oolhqk", "qaebvo", "ubwher", "wyjmqr"}


def test_specific_product_beats_the_broad_icu_fallback():
    # This slug matches BOTH the ECG rule and the \bicu\b fallback. Order must decide.
    permalink, name, _ = I.match("12-lead-ekg-interpretation-icu-nurses-2026")
    assert permalink == "wyjmqr"
    assert "ECG" in name


def test_each_rule_routes_to_its_own_product():
    cases = {
        "acls-code-drugs-2026": "kvppg",
        "abg-interpretation-guide": "avsrc",
        "norepinephrine-titration-icu": "bvezxw",
        "crrt-nursing-guide-2026": "ubwher",
        "chest-tube-management-2026": "itikqo",
        "gi-bleed-icu-management": "dpdvwf",
        "ccrn-exam-dates-2026": "oolhqk",
        "icu-nurse-report-sheet": "qaebvo",
    }
    for slug, expected in cases.items():
        assert I.match(slug)[0] == expected, slug


def test_articles_with_no_honest_product_match_are_left_alone():
    # A mismatched offer is worse than none — these must return None, not the fallback.
    for slug in (
        "roth-ira-for-nurses-complete-guide",
        "travel-nurse-salary-2026",
        "zero-based-budgeting-millennials-2026",
        "nursing-job-interview-guide-2026",
    ):
        assert I.match(slug) is None, slug


def test_block_links_to_the_matched_permalink_and_names_no_price():
    block = I.build("oolhqk", "CCRN Blueprint Study Guide", "Organized around the blueprint.")
    assert f"{I.STORE}/l/oolhqk" in block
    assert 'rel="noopener"' in block
    # Prices live on Gumroad. A hardcoded price here is how the covers drifted to showing
    # $9 on a $14 product — the defect this deliberately cannot reproduce.
    assert "$" not in block


def test_sentinel_wraps_the_block_so_a_rerun_can_detect_it():
    block = I.build("kvppg", "ACLS Code Drug Pocket Card", "One card.")
    assert block.count(f"<!-- {I.SENTINEL} -->") == 1
    assert block.count(f"<!-- /{I.SENTINEL} -->") == 1


# --- claim safety ------------------------------------------------------------
#
# The owner is not a clinician and the site does not employ one. These guard the line
# between "here is a study aid" and "here is something you can rely on at the bedside".

BANNED = [
    "every ",       # completeness claim about medication or content
    "any strip",    # completeness claim
    "all doses",
    "complete guide to",
    "accurate",
    "reliable",
    "trusted",
    "verified",
    "reviewed by",  # the RN-review claim that already cost this site twice
    "licensed",
    "rn-",
    "guarantee",
    "you titrate",  # implies use during patient care
    "at the bedside, ",
    "fastest",
]


def test_no_offer_line_makes_a_clinical_or_completeness_claim():
    for _pattern, _permalink, name, line in I.RULES:
        text = f"{name} {line}".lower()
        for phrase in BANNED:
            assert phrase not in text, f"{name!r} copy contains banned claim {phrase!r}"


def test_every_block_carries_the_not_medical_advice_line():
    for _pattern, permalink, name, line in I.RULES:
        block = I.build(permalink, name, line).lower()
        assert "not medical advice" in block
        assert "verify all doses independently" in block
        assert "created with ai assistance" in block


def test_the_disclaimer_travels_with_the_offer_on_every_edited_article():
    # 94 of the host articles carry no disclaimer of their own, so the block must not
    # depend on the page it lands in.
    for path, html in _articles_with_cta():
        assert "not medical advice" in html.lower(), path


# --- corpus-level invariants -------------------------------------------------


def _articles_with_cta():
    for path in sorted(glob.glob("*.html")):
        html = open(path, encoding="utf-8").read()
        if I.SENTINEL in html:
            yield path, html


def test_no_article_carries_more_than_one_cta():
    for path, html in _articles_with_cta():
        assert html.count(f"<!-- {I.SENTINEL} -->") == 1, path


def test_every_cta_points_at_a_permalink_that_is_live_on_the_store():
    seen = set()
    for path, html in _articles_with_cta():
        for slug in re.findall(r"gumroad\.com/l/([a-z0-9]+)", html):
            assert slug in LIVE, f"{path} links to dead permalink {slug}"
            seen.add(slug)
    # Guard against a rule silently going dark: if a product stops being offered anywhere,
    # that is a decision, not something to discover months later.
    assert seen, "no product CTA found in the corpus at all"


def test_the_cta_never_lands_on_an_article_with_no_matching_rule():
    for path, _ in _articles_with_cta():
        assert I.match(path[:-5].lower()) is not None, path
