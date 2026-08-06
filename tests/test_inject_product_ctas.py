"""
Tests for inject_product_ctas.py.

Rewritten 2026-08-05 when the nine clinical cards were unpublished over bedside-claim
liability and the offers were retargeted to the three career products, which carry none.

Three failure modes matter, and they are not equally bad. Pointing a buy button at a product
nobody can buy is the one a reader actually feels — and it is the one that just happened, so
LIVE below is the real answer from the logged-out storefront, not a guess. Stacking a second
offer on the next run is the one that hits hundreds of files at once (repo rule 3). And
offering a CRNA guide on a wound-care article is the one that makes the site look automated,
so "no match" must stay a real, common outcome.

The corpus-level tests at the bottom guard the invariants going forward.
"""
import glob
import re

import inject_product_ctas as I

# Measured logged-out on icunotebook.gumroad.com, 2026-08-05, AFTER publishing the career
# guides and unpublishing the clinical cards. If a rule ever points outside this set, the
# CTA sends a reader to something they cannot purchase.
LIVE = {"mbuow", "mmscsu", "qdubzb", "kvppg"}

# The three the offers are allowed to use. kvppg is live but is a clinical card pending
# rewritten artwork and study-aid copy, so nothing may route to it yet.
SELLABLE = {"mbuow", "mmscsu", "qdubzb"}


def test_every_rule_points_at_a_product_that_is_actually_buyable():
    for _pattern, permalink, name, _line in I.RULES:
        assert permalink in LIVE, f"{name!r} points at unbuyable {permalink!r}"
        assert permalink in SELLABLE, f"{name!r} routes to a clinical card ({permalink})"


def test_application_intent_beats_the_broad_crna_rule():
    # These slugs match BOTH the application rule and the broad CRNA rule. Order must decide,
    # and it must decide for the $97 guide — that is the in-season, high-intent asset.
    for slug in ("crna-school-personal-statement-examples-guide",
                 "crna-school-interview-questions-2026"):
        assert I.match(slug)[0] == "mbuow", slug


def test_each_rule_routes_to_its_own_product():
    cases = {
        "crna-application-timeline-2026": "mbuow",
        "crna-prerequisite-checklist": "qdubzb",
        "crna-school-cost-2026": "qdubzb",
        "nurse-career-change-options-2026": "mmscsu",
        "utilization-review-nurse-salary": "mmscsu",
    }
    for slug, expected in cases.items():
        assert I.match(slug)[0] == expected, slug


def test_clinical_articles_get_no_offer_now_that_the_cards_are_unpublished():
    # These matched a clinical card before 08-05. They must now return None, not fall back
    # to a career guide — a CRNA planner on a chest-tube article is the automated look.
    for slug in ("chest-tube-management-2026", "abg-interpretation-guide",
                 "norepinephrine-titration-icu", "acls-code-drugs-2026"):
        assert I.match(slug) is None, slug


def test_block_links_to_the_matched_permalink_and_names_no_price():
    block = I.build("mbuow", "The CRNA Application Guide", "GPA benchmarks by program tier.")
    assert f"{I.STORE}/l/mbuow" in block
    assert 'rel="noopener"' in block
    # Prices live on Gumroad. A hardcoded price here is how the covers drifted to showing
    # $9 on a $14 product — the defect this deliberately cannot reproduce.
    assert "$" not in block


def test_sentinel_wraps_the_block_so_a_rerun_can_detect_it():
    block = I.build("qdubzb", "CRNA Prerequisite Planner", "One planning sheet.")
    assert block.count(f"<!-- {I.SENTINEL} -->") == 1
    assert block.count(f"<!-- /{I.SENTINEL} -->") == 1


# --- claim safety ------------------------------------------------------------
#
# Carlos is not a clinician and the site does not employ one. These guard the line between
# "here is a study aid" and "here is something you can rely on at the bedside" — and, for the
# career guides, between "here is what programs look for" and "this gets you accepted".

BANNED = [
    "every ",        # completeness claim
    "complete ",     # completeness claim — also why the product title needs renaming
    "guarantee",
    "accepted applicant",   # outcome claim
    "will get you",
    "ensures",
    "accurate", "reliable", "trusted", "verified",
    "reviewed by",   # the RN-review claim that already cost this site twice
    "licensed",
    "at the bedside",
    "you titrate",
]


def test_no_offer_line_makes_a_clinical_completeness_or_outcome_claim():
    for _pattern, _permalink, name, line in I.RULES:
        text = f"{name} {line}".lower()
        for phrase in BANNED:
            assert phrase not in text, f"{name!r} copy contains banned claim {phrase!r}"


def test_every_block_carries_the_not_medical_advice_line():
    for _pattern, permalink, name, line in I.RULES:
        block = I.build(permalink, name, line).lower()
        assert "not medical advice" in block
        assert "created with ai assistance" in block


# --- the disclaimer has to be about the right risk ---------------------------
#
# Added 2026-08-07. Every product here is a CAREER guide. The block used to close with
# "verify all doses independently", inherited from the clinical line, and shipped that way on
# all 382 articles — telling someone reading about personal statements to check their drug
# doses. A disclaimer aimed at the wrong risk reads as not having read your own page.

CLINICAL_DISCLAIMER_LANGUAGE = [
    "verify all doses",
    "all doses independently",
    "pharmacy reference",
    "institution's protocols",
    "institution&#39;s protocols",
    "clinical judgement",
    "clinical judgment",
]


def test_disclaimer_does_not_talk_about_drug_doses_on_career_products():
    for _pattern, permalink, name, line in I.RULES:
        block = I.build(permalink, name, line).lower()
        for phrase in CLINICAL_DISCLAIMER_LANGUAGE:
            assert phrase.lower() not in block, (
                f"{name!r} carries clinical disclaimer language {phrase!r} — "
                "every product in this table is a career guide")


def test_disclaimer_says_the_one_useful_thing_for_an_applicant():
    block = I.build("mbuow", "The CRNA Application Guide", "GPA benchmarks.").lower()
    assert "verify them with each program directly" in block


def test_no_live_article_still_carries_the_clinical_disclaimer():
    offenders = [p for p, html in _articles_with_cta()
                 if "verify all doses" in html.lower()]
    assert not offenders, f"{len(offenders)} article(s) still carry it, e.g. {offenders[:3]}"


# --- refresh ------------------------------------------------------------------


def _article(block_html):
    return f"<html><body><h1>T</h1><p>intro</p>{block_html}<h2>Body</h2></body></html>"


def test_refresh_rewrites_a_stale_block_in_place():
    stale = _article(
        f"<!-- {I.SENTINEL} -->\n<aside>old copy, verify all doses independently</aside>\n"
        f"<!-- /{I.SENTINEL} -->\n")
    out = I.refresh(stale, "mbuow", "The CRNA Application Guide", "GPA benchmarks.")
    assert "verify all doses" not in out
    assert f"{I.STORE}/l/mbuow" in out
    assert out.count(f"<!-- {I.SENTINEL} -->") == 1, "refresh must not stack a second block"


def test_refresh_is_idempotent():
    # Repo rule 3. Refreshing an already-current block must be a byte-exact no-op, which is
    # what lets --apply be re-run casually without touching 382 files' mtimes.
    current = _article(I.build("qdubzb", "CRNA Prerequisite Planner", "One planning sheet."))
    once = I.refresh(current, "qdubzb", "CRNA Prerequisite Planner", "One planning sheet.")
    twice = I.refresh(once, "qdubzb", "CRNA Prerequisite Planner", "One planning sheet.")
    assert once == current
    assert twice == once


def test_refresh_inserts_replacement_text_literally():
    # A plain string replacement would read backslashes and \\g as group references. A sed
    # swap with the same flaw put mangled text on a live product page on 2026-08-07.
    out = I.refresh(
        _article(f"<!-- {I.SENTINEL} -->\n<aside>old</aside>\n<!-- /{I.SENTINEL} -->\n"),
        "mmscsu", r"Kit \1 & \g<0>", r"Back\slash and & ampersand.")
    assert r"Kit \1 & \g<0>" in out
    assert r"Back\slash and & ampersand." in out


# --- corpus-level invariants -------------------------------------------------


def _articles_with_cta():
    for path in sorted(glob.glob("*.html")):
        html = open(path, encoding="utf-8").read()
        if I.SENTINEL in html:
            yield path, html


def test_no_article_carries_more_than_one_cta():
    for path, html in _articles_with_cta():
        assert html.count(f"<!-- {I.SENTINEL} -->") == 1, path


def test_no_injected_offer_points_at_an_unbuyable_product():
    seen = set()
    for path, html in _articles_with_cta():
        block = re.search(
            rf"<!-- {I.SENTINEL} -->(.*?)<!-- /{I.SENTINEL} -->", html, re.S)
        assert block, path
        for slug in re.findall(r"gumroad\.com/l/([a-z0-9]+)", block.group(1)):
            assert slug in SELLABLE, f"{path} offers unbuyable/clinical {slug}"
            seen.add(slug)
    # Guard against a rule silently going dark: if a product stops being offered anywhere,
    # that is a decision, not something to discover months later.
    assert seen, "no product CTA found in the corpus at all"


def test_the_cta_never_lands_on_an_article_with_no_matching_rule():
    for path, _ in _articles_with_cta():
        assert I.match(path[:-5].lower()) is not None, path
