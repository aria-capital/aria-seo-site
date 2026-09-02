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
# RETARGETED 2026-08-23. Destinations are Etsy listings now, not Gumroad slugs — Gumroad
# payouts have been frozen since 2026-07-13 pending an SSN, so a sale there reaches nobody.
# The three below were read from the shop's own RSS feed the day of the switch, which is the
# credential-free instrument for this shop: a datacentre fetch of an Etsy /listing/ URL
# returns 403 for real and invented ids alike and proves nothing either way.
GUIDE = "https://www.etsy.com/listing/4560718026/crna-application-guide-2027-cycle-icu"
PLANNER = "https://www.etsy.com/listing/4560699705/crna-prerequisite-planner-track-icu"
PIVOT = "https://www.etsy.com/listing/4559192954/beyond-the-bedside-nurse-career-pivot"
WORKSHEET = "https://www.etsy.com/listing/4560725032/crna-program-comparison-worksheet"

# REPORT SHEETS, added 2026-09-02. Read from the shop's own RSS feed that day — the same
# credential-free instrument the rest of this file uses, and the only one available: the Etsy
# shop page and /listing/ URLs both return 403 to a datacentre fetch, for real and invented ids
# alike. The feed returned ten items carrying these seven ids and their exact titles.
#
# One caution recorded because it nearly produced a wrong answer that day: this feed is CAPPED
# at ten items. PIVOT (4559192954) was absent from it and that absence proves nothing about
# whether it is live — Etsy's own seller mail on 2026-09-02 named "Beyond the Bedside" as a
# listing wanting a video, which is how it was confirmed still sellable. Do not read absence
# from a capped feed as a delisting.
ICU_SHEET = "https://www.etsy.com/listing/4567558734/icu-nurse-report-sheet-critical-care"
ER_SHEET = "https://www.etsy.com/listing/4567544361/er-nurse-report-sheet-emergency"
CNA_SHEET = "https://www.etsy.com/listing/4567566458/cna-report-sheet-nurse-aide-brain-sheet"
STUDENT_SHEET = "https://www.etsy.com/listing/4567561046/nursing-student-clinical-paperwork"
MEDSURG_SHEET = "https://www.etsy.com/listing/4567531245/med-surg-nurse-report-sheet-nursing"
SBAR_SHEET = "https://www.etsy.com/listing/4567539159/sbar-nurse-report-sheet-sbar-handoff"
BUNDLE_SHEET = "https://www.etsy.com/listing/4567527501/nurse-report-sheet-bundle-nursing-brain"
SHEETS = {ICU_SHEET, ER_SHEET, CNA_SHEET, STUDENT_SHEET, MEDSURG_SHEET, SBAR_SHEET, BUNDLE_SHEET}

SELLABLE = {GUIDE, PLANNER, PIVOT, WORKSHEET} | SHEETS

# Slugs measured DEAD on 2026-08-07 — six 404s plus two unpublished. 117 live article pages
# were still linking to these, which is what prompted the sweep. Nothing may ever route here.
# `vrseeu` joined them 2026-08-23 for a different and worse reason: it is not dead, it is
# LIVE and buyable and under the 2026-08-19 clinical hold for a wrong atropine dose and a
# tenfold epinephrine discrepancy. Unbuyable and must-not-be-bought both end here.
DEAD = {"qaebvo", "bvezxw", "wyjmqr", "ubwher", "itikqo", "avsrc", "kvppg", "dpdvwf", "vrseeu"}


def test_every_rule_points_at_a_product_that_is_actually_buyable():
    for _pattern, dest, name, _line in I.RULES:
        assert dest in SELLABLE, f"{name!r} routes to a destination not on the sellable list ({dest})"
        for slug in DEAD:
            assert slug not in dest, f"{name!r} routes to a DEAD or HELD slug ({slug})"


def test_application_intent_beats_the_broad_crna_rule():
    # These slugs match BOTH the application rule and the broad CRNA rule. Order must decide,
    # and it must decide for the $97 guide — that is the in-season, high-intent asset.
    for slug in ("crna-school-personal-statement-examples-guide",
                 "crna-school-interview-questions-2026"):
        assert I.match(slug)[0] == "https://www.etsy.com/listing/4560718026/crna-application-guide-2027-cycle-icu", slug


def test_each_rule_routes_to_its_own_product():
    # Destinations became full URLs on 2026-08-23 when the table was retargeted from Gumroad
    # (payouts frozen since 07-13) to Etsy. Asserting the URL rather than an opaque slug is
    # the point: this test now says where a reader actually lands.
    # `crna-school-cost-2026` moved from PLANNER to WORKSHEET on 2026-08-28 and this case was
    # never updated, so this test has been RED on the branch ever since — alongside two others,
    # for the same root cause: the worksheet rule was added to inject_product_ctas.py and never
    # added to SELLABLE here. Five days of a guard reporting a failure nobody read. Repo rule:
    # check the exit code directly, never `| tail`.
    cases = {
        "crna-application-timeline-2026": GUIDE,
        "crna-prerequisite-checklist": PLANNER,
        "crna-school-cost-2026": WORKSHEET,
        "best-crna-programs-2026": WORKSHEET,
        "nurse-career-change-options-2026": PIVOT,
        "utilization-review-nurse-salary": PIVOT,
        # report sheets, 2026-09-02
        "abg-interpretation-icu-nurses-2026": ICU_SHEET,
        "er-nurse-triage-tips-2026": ER_SHEET,
        "cna-daily-care-checklist": CNA_SHEET,
        "nursing-student-clinical-guide": STUDENT_SHEET,
        "med-surg-nurse-ratios-2026": MEDSURG_SHEET,
        "nursing-handoff-sbar-guide-2026": SBAR_SHEET,
    }
    for slug, expected in cases.items():
        assert I.match(slug)[0] == expected, slug


def test_no_rule_points_at_the_channel_that_cannot_pay():
    # Gumroad froze payouts 2026-07-13 pending an SSN only Carlos can supply. A CTA sending a
    # reader there is a sale he does not receive. This fails loudly if any rule drifts back.
    assert "gumroad" not in str(I.RULES).lower(), (
        "A rule points at Gumroad. Payouts there are frozen; Etsy pays weekly from sale one."
    )
    for _pattern, dest, _name, _line in I.RULES:
        assert dest.startswith("https://www.etsy.com/listing/"), dest


def test_a_clinical_article_is_never_offered_a_product_that_prints_doses():
    # RE-AIMED 2026-09-02, and this is the one guard in this file that changed meaning, so the
    # reasoning is set out in full rather than summarised.
    #
    # It was `test_clinical_articles_get_no_offer_while_the_hold_stands`, asserting match() is
    # None for clinical slugs. That was the correct assertion for as long as the ONLY product a
    # clinical article could be offered was `vrseeu`, the ICU Reference Set. Read the reason it
    # was written: "An offer here is not a wasted click, it is a sale of a file with a wrong
    # dose in it to an ICU nurse." The 08-19 hold is about DOSES PRINTED IN A PRODUCT —
    # bradycardia atropine at 0.5 mg where the algorithm has said 1 mg since 2020, printed
    # twice; and an epinephrine line whose two options differ tenfold.
    #
    # The ICU Report Sheet is a blank form with ruled boxes. It prints no dose, no protocol and
    # no reference value, so there is no wrong number in it to sell to anyone. The hold's
    # reasoning does not reach it, and asserting None here would have blocked 445 articles from
    # any offer on the strength of a rule aimed at a different object.
    #
    # So the invariant is restated as the thing that actually matters, and it is STRICTER than
    # a None check in the way that counts: a clinical article must never be routed to a
    # dose-carrying destination, whether or not one is ever added back to the table. A future
    # session that re-adds a dose-carrying product fails here even if it also adds a rule that
    # would have satisfied the old "must be None" form by accident.
    #
    # `vrseeu` itself stays permanently barred by the untouched test below.
    for slug in ("chest-tube-management-2026", "abg-interpretation-guide",
                 "norepinephrine-titration-icu", "acls-code-drugs-2026",
                 "vasopressor-titration-icu-nurses-2026", "crrt-troubleshooting-2026"):
        hit = I.match(slug)
        if hit is None:
            continue
        dest = hit[0]
        for slug_of_a_dose_product in DEAD:
            assert slug_of_a_dose_product not in dest, (
                f"{slug} routes to {dest}, which carries the dose-product slug "
                f"{slug_of_a_dose_product!r}")
        assert dest in SHEETS, (
            f"{slug} is a clinical article and was offered {dest}. Only a blank report sheet "
            "may be offered on clinical pages — a guide that makes claims about practice, or "
            "any product printing doses, may not.")


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
        assert hit is None or hit[0] not in {"https://www.etsy.com/listing/4560718026/crna-application-guide-2027-cycle-icu", "https://www.etsy.com/listing/4560699705/crna-prerequisite-planner-track-icu", "https://www.etsy.com/listing/4559192954/beyond-the-bedside-nurse-career-pivot"}, slug


def test_the_subject_of_the_article_beats_the_word_icu_in_its_name():
    # icu-nurse-salary-*.html matched the clinical rule before 08-07 and was offered an ABG
    # reference. Career rules sit above the clinical one so the SUBJECT wins over the setting.
    for slug in ("icu-nurse-salary-2026", "icu-nurse-salary-by-state-2026",
                 "icu-nurse-interview-questions-2026", "second-career-nursing-guide-2026"):
        assert I.match(slug)[0] == "https://www.etsy.com/listing/4559192954/beyond-the-bedside-nurse-career-pivot", slug


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
    block = I.build(GUIDE, "The CRNA Application Guide", "GPA benchmarks by program tier.")
    assert GUIDE in block
    assert 'rel="noopener"' in block
    # Prices live on the storefront. A hardcoded price here is how the covers drifted to showing
    # $9 on a $14 product — the defect this deliberately cannot reproduce.
    assert "$" not in block


def test_sentinel_wraps_the_block_so_a_rerun_can_detect_it():
    block = I.build(PLANNER, "CRNA Prerequisite Planner", "One planning sheet.")
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
    block = I.build(GUIDE, "The CRNA Application Guide", "GPA benchmarks.").lower()
    assert "verify them with each program directly" in block


# --- report sheets, 2026-09-02 ------------------------------------------------


def test_sheet_destinations_cannot_drift_from_the_rules_table():
    # note_for() picks the closing note by destination, so a report-sheet URL that is in RULES
    # but missing from SHEET_DESTS would silently ship the admissions disclaimer on a brain
    # sheet — the exact 08-07 defect, reintroduced by omission rather than by copy-paste.
    in_rules = {dest for _p, dest, _n, _l in I.RULES if dest in SHEETS}
    assert I.SHEET_DESTS == SHEETS, "SHEET_DESTS and this file's SHEETS list disagree"
    assert in_rules <= I.SHEET_DESTS, f"routed but not in SHEET_DESTS: {in_rules - I.SHEET_DESTS}"


def test_a_report_sheet_gets_the_stationery_note_and_not_the_admissions_one():
    block = I.build(ICU_SHEET, "ICU Nurse Report Sheet", "One and two patient layouts.").lower()
    assert "not medical advice" in block
    assert "patient-privacy policy" in block
    assert "program requirements" not in block, (
        "a brain sheet is carrying the CRNA admissions disclaimer — wrong risk, 08-07 lesson")


def test_a_career_guide_never_gets_the_stationery_note():
    block = I.build(GUIDE, "The CRNA Application Guide", "GPA benchmarks.").lower()
    assert "patient-privacy policy" not in block


def test_sheet_rules_are_appended_after_every_career_rule():
    # This is what makes the 2026-09-02 change provably non-disruptive, and it is a structural
    # property rather than a spot check: first-match-wins means a rule appended AFTER all the
    # career rules can only ever catch articles that previously matched nothing. Interleave one
    # sheet rule above a career rule and articles silently change destination in bulk — which
    # is how 546 pages moved unnoticed once already.
    kinds = ["sheet" if dest in SHEETS else "career" for _p, dest, _n, _l in I.RULES]
    if "sheet" not in kinds:
        return
    first_sheet = kinds.index("sheet")
    assert "career" not in kinds[first_sheet:], (
        "a career rule sits below a report-sheet rule; appending is no longer safe and the "
        "sheet rule may now shadow it")


def test_the_career_products_still_win_on_the_articles_that_are_about_careers():
    # The ICU sheet rule matches the word `icu`, which appears in salary and interview slugs.
    # Career rules sit above it, so the SUBJECT of the article still wins over the setting in
    # its name — the same invariant the 08-07 note describes, re-checked against the new table.
    for slug in ("icu-nurse-salary-2026", "icu-nurse-interview-questions-2026"):
        assert I.match(slug)[0] == PIVOT, slug
    assert I.match("crna-prerequisite-checklist")[0] == PLANNER


def test_personal_finance_articles_are_still_offered_nothing():
    # 546 articles still match no rule and that is the correct outcome, not a gap to close.
    # A nurse reading about a Roth IRA is not shopping for a brain sheet, and a mismatched
    # offer is worse than none.
    for slug in ("roth-ira-for-nurses-complete-guide", "nurse-budget-template-2026",
                 "student-loan-forgiveness-nurses-2026"):
        assert I.match(slug) is None, slug


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
    out = I.refresh(stale, GUIDE, "The CRNA Application Guide", "GPA benchmarks.")
    assert "verify all doses" not in out
    assert GUIDE in out
    assert out.count(f"<!-- {I.SENTINEL} -->") == 1, "refresh must not stack a second block"


def test_refresh_is_idempotent():
    # Repo rule 3. Refreshing an already-current block must be a byte-exact no-op, which is
    # what lets --apply be re-run casually without touching 382 files' mtimes.
    current = _article(I.build(PLANNER, "CRNA Prerequisite Planner", "One planning sheet."))
    once = I.refresh(current, PLANNER, "CRNA Prerequisite Planner", "One planning sheet.")
    twice = I.refresh(once, PLANNER, "CRNA Prerequisite Planner", "One planning sheet.")
    assert once == current
    assert twice == once


def test_refresh_inserts_replacement_text_literally():
    # A plain string replacement would read backslashes and \\g as group references. A sed
    # swap with the same flaw put mangled text on a live product page on 2026-08-07.
    out = I.refresh(
        _article(f"<!-- {I.SENTINEL} -->\n<aside>old</aside>\n<!-- /{I.SENTINEL} -->\n"),
        PIVOT, r"Kit \1 & \g<0>", r"Back\slash and & ampersand.")
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
        for href in re.findall(r'href="([^"]+)"', block.group(1)):
            if not href.startswith("http"):
                continue
            assert href in SELLABLE, f"{path} offers a destination not on the sellable list: {href}"
            for dead in DEAD:
                assert dead not in href, f"{path} offers DEAD/HELD {dead}"
            seen.add(href)
    # Guard against a rule silently going dark: if a product stops being offered anywhere,
    # that is a decision, not something to discover months later.
    assert seen, "no product CTA found in the corpus at all"


def test_the_cta_never_lands_on_an_article_with_no_matching_rule():
    for path, _ in _articles_with_cta():
        assert I.match(path[:-5].lower()) is not None, path
