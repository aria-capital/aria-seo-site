#!/usr/bin/env python3
"""Put a matching product in front of the reader, instead of a generic nav link.

Every article currently offers only "Resources" in the top nav. This inserts one
topic-matched offer block into the body of each article whose subject actually
maps to a product we sell. Articles with no genuine match are LEFT ALONE — a
mismatched offer is worse than none.

Idempotent (sentinel comment), reversible (git), and it never invents a price:
prices live on Gumroad and are not duplicated here, so this file can never drift
out of sync with the store the way the covers did.

    python3 inject_product_ctas.py --dry-run
    python3 inject_product_ctas.py --apply
"""
import re
import sys
import glob

from safe_write import safe_write_html

# RETARGETED TO ETSY, 2026-08-23. Rules used to carry a Gumroad slug and the block built the
# href as f"{STORE}/l/{slug}". They now carry the FULL destination URL, for two reasons.
#
# 1. Gumroad cannot pay him. Payouts have been frozen since 2026-07-13 pending an SSN, so
#    money landing there does not reach him. Etsy deposits weekly from the first sale. This
#    site was sending 950 links to the channel that cannot pay and 33 to the one that can.
# 2. A slug plus a hardcoded store is a destination this table cannot state. Whoever moves a
#    product next has to edit a format string in the template instead of the row that names
#    the product — which is how a table and a corpus drift apart without either looking wrong.
#
# The URLs below are the canonical slugged forms taken from the shop's own RSS feed on
# 2026-08-23 (the credential-free instrument for this shop; a datacentre fetch of an Etsy
# /listing/ URL returns 403 for real and invented ids alike and carries no information).
STORE = "https://icunotebook.gumroad.com"  # retained only for the legacy/held-block matchers
SENTINEL = "aria-product-cta"

# Ordered, most specific first — first match wins.
# (regex over the filename slug, permalink, product name, one honest line)
#
# COPY RULE, and it is not a style preference: every line below describes the FORMAT and
# SUBJECT of a study aid. None of them claims completeness, clinical authority, accuracy,
# or fitness for patient care. Words deliberately removed after review on 2026-08-05:
#   "Every code-cart drug"   -> a completeness claim about emergency medication
#   "read ANY strip"         -> a completeness claim
#   "escalate fastest"       -> a clinical judgement the site cannot support
#   "the infusions YOU TITRATE" / "instead of from memory" -> implies bedside practice use
# We are not clinicians and the site does not employ one. Describe the object, never the
# clinical outcome. See CLAUDE.md standing priority 1 and 5: prefer removing a claim over
# qualifying it.
#
#
# LIVE PRODUCTS ONLY — verified on the logged-out storefront 2026-08-05.
# The nine clinical cards were unpublished that day over bedside-claim liability, so every
# rule that pointed at one has been REMOVED rather than left to send readers at something
# they cannot buy. A CTA for an unbuyable product is a wasted click and a broken promise.
# When the clinical line returns with fixed artwork and study-aid copy, restore those rules
# here — the machinery is unchanged, only this table moved.
#
RULES = [
    # $97 — the flagship. CRNA application season runs Aug-Dec; this is the in-season asset.
    (r"crna-school-application|crna-application|personal-statement|crna-school-interview|"
     r"crna-admission|crna-school-acceptance|crna-essay|letters-of-recommendation|"
     r"crna-school-resume|crna-shadow|crna-school-requirements|get-into-crna",
     "https://www.etsy.com/listing/4560718026/crna-application-guide-2027-cycle-icu",
     "The CRNA Application Guide",
     "GPA benchmarks by program tier, a personal-statement framework, interview questions "
     "and an 18-month application calendar."),
    # $8.99 — ADDED 2026-08-28. This listing (4560725032, published 08-22) was linked from
    # ZERO of the 1,462 pages: it was never added to this table, so the site sold three of the
    # shop's four products and did not know the fourth existed. Meanwhile ~34 pages whose whole
    # subject is *choosing between schools* — best-crna-programs-ranked-by-cost,
    # cheapest-crna-schools, crna-school-cost — were falling through to the Prerequisite Planner
    # below, because that rule's `crna\b` catches every CRNA page on the site.
    #
    # It sits ABOVE the planner deliberately, same reason the career rules sit above the
    # clinical one: the subject of the article should win over a broad keyword inside it.
    #
    # The pattern is written from what the PRODUCT is (compare programs on cost, pass rate,
    # length), not from the filenames it happened to match — the classifier that was fitted to
    # its own 13 cases and then declined all 5 real ones is the cautionary tale here. Note it
    # deliberately does NOT match `crna-vs-anesthesiologist`, `crna-vs-np` or `aa-vs-crna`:
    # those compare CAREERS, not schools, and belong where they already point.
    (r"best-crna-(programs|schools)|crna-(programs|schools)-ranked|cheapest-crna|"
     r"crna-school-cost|crna-program-comparison|crna-school-comparison|compare-crna-"
     r"|crna-(programs|schools)-by-state|crna-acceptance-rate|crna-pass-rate|"
     r"crna-program-length|crna-school-list",
     "https://www.etsy.com/listing/4560725032/crna-program-comparison-worksheet",
     "CRNA Program Comparison Worksheet",
     "Put the schools you are considering side by side on cost, pass rate and length — "
     "the three numbers that decide it — on one printable sheet."),
    # $19.99 — earlier in the same journey: prerequisites, GPA repair, timing.
    (r"crna-prereq|prerequisite|crna-school-cost|crna-gpa|science-gpa|crna-timeline|"
     r"icu-experience|crna-programs|crna-school|crna\b|nurse-anesthet",
     "https://www.etsy.com/listing/4560699705/crna-prerequisite-planner-track-icu",
     "CRNA Prerequisite Planner",
     "Track the prerequisites, science GPA and ICU hours each program expects, "
     "on one planning sheet."),
    # $27 — for nurses leaving the bedside who are not going the CRNA route.
    # `salary`, `second-career` and `interview-questions` added 2026-08-07: without them,
    # icu-nurse-salary-*.html and icu-nurse-interview-questions.html fell through to the
    # clinical rule below and were offered an ABG reference. Career rules sit ABOVE the
    # clinical one precisely so the subject of the article wins over the word "icu" in it.
    (r"career-change|leave-bedside|beyond-the-bedside|non-bedside|nurse-career|career-pivot|"
     r"nursing-jobs|job-interview|interview-questions|resume|salary|second-career|"
     r"informatics|case-management|utilization-review|"
     r"infection-control|legal-nurse|nurse-educator|travel-nurse|per-diem",
     "https://www.etsy.com/listing/4559192954/beyond-the-bedside-nurse-career-pivot",
     "Beyond the Bedside — Nurse Career Pivot Kit",
     "Non-bedside nursing paths, what each one pays, and how to position your ICU "
     "experience for them."),
    # THE CLINICAL RULE IS REMOVED, 2026-08-23. It pointed at `vrseeu` ("The ICU Reference
    # Set"), the bundle built from the nine cards, and it had reached 546 articles — the
    # single most-linked destination on this site.
    #
    # It comes out because of `DO-NOT-SELL — clinical hold 2026-08-19`, which audited those
    # cards dose by dose against the issuing bodies' current documents. Two findings sit on
    # the ACLS card inside this bundle and either one is enough on its own:
    #   * bradycardia atropine printed as 0.5 mg. It has been 1 mg since the 2020 algorithm,
    #     and it is printed TWICE in two different sections, so correcting one leaves the
    #     other live.
    #   * `1 mg IV (10 mL of 0.1 mg/mL or 1 mL of 1:10,000)` — 1 mL of 1:10,000 is 0.1 mg.
    #     Two options for the same drug differing by tenfold, on the most important drug in
    #     a code.
    #
    # This is the same move the 2026-08-05 note above describes, for a stronger reason. That
    # removal was about a product readers could not buy. This one is about a product they
    # CAN buy, and should not: `l/vrseeu` returned HTTP 200 on 2026-08-23 with the deleted
    # `l/itikqo` returning 404 as the control, so the 200 means what it says.
    #
    # DO NOT restore this rule on the strength of a model re-reading the file. The hold's own
    # bar is a named clinician with current credentials signing off, or a product that
    # carries no doses. Neither has happened. Restoring it re-links 546 pages in one run.
]

# LEGACY BLOCK, removed 2026-08-07. Before this machinery existed, a different CTA was
# stamped onto 117 clinical articles between <!-- gumroad-cta --> markers. Two things were
# wrong with it and both were live:
#   1. Its link pointed at a product that no longer exists. Six slugs (qaebvo, bvezxw,
#      wyjmqr, ubwher, itikqo, avsrc) return HTTP 404 on the store, and two more
#      (kvppg, dpdvwf) return 200 but are unpublished. 117 pages, every buying click wasted.
#   2. It read "Need this at the bedside? ... fits in your scrubs pocket" — the exact
#      bedside-use framing the clinical line was pulled for on 2026-08-05.
# Excised here rather than patched: the block is obsolete, not merely wrong, and leaving a
# second CTA style alive is how a fix reaches 382 pages and misses 117.
LEGACY_RE = re.compile(r"[ \t]*<!-- gumroad-cta -->.*?<!-- /gumroad-cta -->\n?", re.S)

# HELD PRODUCT, 2026-08-23. Removing the rule above stops NEW blocks being written, but it
# does nothing about the 546 already stamped into articles — those pages simply stop matching
# any rule and get skipped, block intact. So the strip has to be its own unconditional pass,
# exactly like the legacy one and for the same reason written there: a link to something a
# reader should not buy must be removed whether or not we have anything to put in its place.
#
# Scoped by the slug appearing INSIDE a sentinel span, so it can never eat a career block.
# Verified before running: all 546 occurrences of l/vrseeu sit inside a sentinel span, none
# outside, one span per file.
HELD_SLUG = "l/vrseeu"
HELD_RE = re.compile(
    rf"[ \t]*<!-- {SENTINEL} -->(?:(?!<!-- /{SENTINEL} -->).)*?{re.escape(HELD_SLUG)}"
    rf".*?<!-- /{SENTINEL} -->\n?",
    re.S,
)

# DISCLAIMER RULE, learned 2026-08-07. All three products are CAREER guides. The block used to
# close with "not a substitute for your institution's protocols, pharmacy references, or
# clinical judgement — verify all doses independently", copied from the clinical line. On a
# personal-statement article that sentence is nonsense, and it was live on all 382 of them.
# A disclaimer aimed at the wrong risk is not a cautious disclaimer, it is a visible mistake:
# it tells a CRNA applicant we were not reading our own page. Match the disclaimer to the
# product's actual risk — here, admissions guidance that can go stale — and say the one useful
# thing instead: program requirements vary, check them at the source.
BLOCK = """<!-- {sentinel} -->
<aside style="border:1px solid #d7e3f4;border-left:4px solid #0057b8;background:#f7fafd;border-radius:6px;padding:18px 20px;margin:28px 0;">
  <p style="margin:0 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#5b7a9d;">From The ICU Notebook</p>
  <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#0d2a45;">{name}</p>
  <p style="margin:0 0 12px;font-size:14px;line-height:1.5;color:#41576e;">{line}</p>
  <a href="{url}" target="_blank" rel="noopener"
     style="display:inline-block;padding:9px 16px;background:#0057b8;color:#fff;text-decoration:none;border-radius:5px;font-size:14px;font-weight:600;">See what's on it &rarr;</a>
  <p style="margin:12px 0 0;font-size:12px;line-height:1.5;color:#6b7f94;">Study material for nurses. Created with AI assistance. Not medical advice, and not admissions, career or financial advice. Program requirements and deadlines vary &mdash; verify them with each program directly.</p>
</aside>
<!-- /{sentinel} -->
"""


def build(url, name, line):
    return BLOCK.format(sentinel=SENTINEL, name=name, line=line, url=url)


def match(slug):
    for pattern, permalink, name, line in RULES:
        if re.search(pattern, slug):
            return permalink, name, line
    return None


BLOCK_RE = re.compile(rf"<!-- {SENTINEL} -->.*?<!-- /{SENTINEL} -->\n?", re.S)


def refresh(html, permalink, name, line):
    """Re-emit an existing block from the current template.

    Follows the repair pattern in CLAUDE.md: excise the region between its own markers and
    re-emit a canonical copy, so the no-op case is exact and a re-run changes nothing. This
    is what lets a copy fix — like the 08-07 disclaimer — reach the 382 articles that already
    carry a block, instead of needing a throwaway repair script that itself needs a test.

    Uses a replacement *function* so the new text is inserted literally: a plain string
    replacement would treat backslashes as group references. The same class of bug put
    mangled text on a live product page the day this was written.
    """
    return BLOCK_RE.sub(lambda _m: build(permalink, name, line), html, count=1)


def main():
    apply_changes = "--apply" in sys.argv
    if not apply_changes and "--dry-run" not in sys.argv:
        print("pass --dry-run or --apply")
        return 2

    counts = {}
    skipped_nomatch = skipped_noanchor = 0
    added = refreshed = unchanged = legacy_removed = held_removed = 0

    for path in sorted(glob.glob("*.html")):
        slug = path[:-5].lower()
        html = open(path, encoding="utf-8").read()

        # Strip the obsolete block first, on EVERY article — including ones with no product
        # match. A dead buy-link is worse than no offer, so its removal must not depend on
        # having something to put in its place.
        if "<!-- gumroad-cta -->" in html:
            stripped = LEGACY_RE.sub("", html)
            if stripped != html:
                html = stripped
                legacy_removed += 1
                if apply_changes and not match(slug):
                    safe_write_html(path, html, allow_preexisting=True)

        # Strip any block pointing at the HELD product, on EVERY article, for the same reason
        # and by the same rule as the legacy strip directly above. This must run before the
        # match: with the clinical rule gone those 546 pages match nothing, so without this
        # they would be skipped with the block still in them.
        if HELD_SLUG in html:
            stripped = HELD_RE.sub("", html)
            if stripped != html:
                html = stripped
                held_removed += 1
                if apply_changes and not match(slug):
                    safe_write_html(path, html, allow_preexisting=True)

        hit = match(slug)
        if not hit:
            skipped_nomatch += 1
            continue
        permalink, name, line = hit

        if SENTINEL in html:
            new = refresh(html, permalink, name, line)
            if new == html:
                unchanged += 1
                continue
            refreshed += 1
        elif html != open(path, encoding="utf-8").read() and not re.search(r"<h2[\s>]", html):
            # legacy block stripped but nothing to anchor a replacement to — still a win
            if apply_changes:
                safe_write_html(path, html, allow_preexisting=True)
            skipped_noanchor += 1
            continue
        else:
            # Insert above the first <h2 — after the headline and intro, high on the page.
            anchor = re.search(r"<h2[\s>]", html)
            if not anchor:
                skipped_noanchor += 1
                continue
            at = anchor.start()
            new = html[:at] + build(permalink, name, line) + html[at:]
            added += 1

        counts[name] = counts.get(name, 0) + 1
        if apply_changes:
            # Repo rule 1: never raw open(...,'w') on an article. This is a bulk edit
            # of pre-existing files, so allow_preexisting=True — refuse only on regression.
            safe_write_html(path, new, allow_preexisting=True)

    total = added + refreshed
    print(("APPLIED" if apply_changes else "DRY RUN")
          + f" — {total} article(s) to write ({added} new, {refreshed} refreshed)\n")
    for name in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {counts[name]:5d}  {name}")
    print(f"\n  {legacy_removed:5d}  obsolete <!-- gumroad-cta --> block(s) removed (dead links + bedside framing)")
    print(f"  {held_removed:5d}  HELD-product block(s) removed (l/vrseeu — clinical hold 2026-08-19)")
    print(f"  {unchanged:5d}  already correct (idempotent no-op)")
    print(f"  {skipped_nomatch:5d}  no matching product — deliberately left alone")
    print(f"  {skipped_noanchor:5d}  no <h2> anchor — skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
