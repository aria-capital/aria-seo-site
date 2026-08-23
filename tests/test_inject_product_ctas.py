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

# Re-measured logged-out on icunotebook.gumroad.com, 2026-08-07. The clinical line came back
# that week — not as the nine cards, but as ONE 33-page study bundle (`vrseeu`) with redrawn
# artwork and study-aid copy, which is the condition the 08-05 note set for restoring it. The
# nine individual cards stay unbuyable: `kvppg` and `dpdvwf` return HTTP 200 but
# `is_published=false`, and six more slugs are hard 404s.
#
# The guarantee this file exists to enforce has NOT changed: a buy button must never point at
# something a reader cannot purchase. Only the measurement behind it has.
LIVE = {"mbuow", "mmscsu", "qdubzb", "vrseeu", "wkcbuc"}

# Everything live may be offered. kvppg is deliberately absent: it is unpublished, and it was
# the single highest-liability listing in the catalogue.
SELLABLE = {"mbuow", "mmscsu", "qdubzb", "vrseeu", "wkcbuc"}

# Slugs measured DEAD on 2026-08-07 — six 404s plus two unpublished. 117 live article pages
# were still linking to these, which is what prompted the sweep. Nothing may ever route here.
DEAD = {"qaebvo", "bvezxw", "wyjmqr", "ubwher", "itikqo", "avsrc", "kvppg", "dpdvwf"}


def test_every_rule_points_at_a_product_that_is_actually_buyable():
    for _pattern, permalink, name, _line in I.RULES:
        assert permalink in LIVE, f"{name!r} points at unbuyable {permalink!r}"
        assert permalink in SELLABLE, f"{name!r} routes to a product we may not offer ({permalink})"
        assert permalink not in DEAD, f"{name!r} routes to a DEAD slug ({permalink})"


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


def test_clinical_articles_get_no_offer_while_the_hold_stands():
    # REPLACES test_clinical_articles_now_route_to_the_restored_study_bundle, 2026-08-23.
    # The right answer for these slugs has now been None twice, for two different reasons.
    # From 08-05 to 08-07 it was None because the clinical products were unpublished and an
    # offer would have been a dead end. It is None again from 08-23, and this reason is much
    # worse than a dead end: `vrseeu` is LIVE and buyable, and the 08-19 clinical hold found
    # bradycardia atropine printed as 0.5 mg (1 mg since 2020, printed twice) and an
    # epinephrine line whose two options differ by tenfold. An offer here is not a wasted
    # click, it is a sale of a file with a wrong dose in it to an ICU nurse.
    for slug in ("chest-tube-management-2026", "abg-interpretation-guide",
                 "norepinephrine-titration-icu", "acls-code-drugs-2026"):
        assert I.match(slug) is None, f"{slug} was offered a product while the hold stands"


def test_the_held_product_cannot_be_reached_from_the_rules_table():
    # A regression guard, not a style check. Restoring one line to RULES re-links 546
    # articles in a single run, and the run reports it as a routine refresh. Any future
    # session that wants this rule back has to delete this test first, and deleting a test
    # named this is a decision rather than an oversight.
    assert "vrseeu" not in str(I.RULES), (
        "The held product is back in RULES. The hold's bar is a named clinician with "
        "current credentials signing off, or a product carrying no doses — see the dated "
        "note in inject_product_ctas.py."
    )
    assert I.HELD_SLUG == "l/vrseeu"


def test_a_career_guide_is_never_offered_on_a_clinical_article():
    # `match()` returns None for clinical slugs while the hold stands, so this asserts on the
    # hit itself rather than subscripting it — the point is that a chest-tube article must
    # never be handed a CRNA planner, whether or not any clinical rule exists.
    for slug in ("chest-tube-management-2026", "abg-interpretation-guide",
                 "vasopressor-titration-icu-nurses-2026", "crrt-troubleshooting-2026"):
        hit = I.match(slug)
        assert hit is None or hit[0] not in {"mbuow", "mmscsu", "qdubzb"}, slug


def test_the_subject_of_the_article_beats_the_word_icu_in_its_name():
    # icu-nurse-salary-*.html matched the clinical rule before 08-07 and was offered an ABG
    # reference. Career rules sit above the clinical one so the SUBJECT wins over the setting.
    for slug in ("icu-nurse-salary-2026", "icu-nurse-salary-by-state-2026",
                 "icu-nurse-interview-questions-2026", "second-career-nursing-guide-2026"):
        assert I.match(slug)[0] == "mmscsu", slug


def test_the_obsolete_bedside_block_is_excised_whole():
    # 401 articles carried a pre-machinery CTA reading "Need this at the bedside? ... fits in
    # your scrubs pocket", 117 of them linking a product that 404s. Removal must take the
    # whole block including both markers, and must leave the rest of the document alone.
    page = ('<h1>T</h1>\n<p>before</p>\n'
            '<!-- gumroad-cta -->\n<div><p>Need this at the bedside?</p>\n'
            '<a href="https://icunotebook.gumroad.com/l/wyjmqr">Get the Reference Card</a>\n'
            '</div>\n<!-- /gumroad-cta -->\n<p>after</p>\n')
    out = I.LEGACY_RE.sub("", page)
    assert "gumroad-cta" not in out
    assert "bedside" not in out
    assert "wyjmqr" not in out
    assert "<p>before</p>" in out and "<p>after</p>" in out


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
