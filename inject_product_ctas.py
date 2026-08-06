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

STORE = "https://icunotebook.gumroad.com"
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
     "mbuow", "The CRNA Application Guide",
     "GPA benchmarks by program tier, a personal-statement framework, interview questions "
     "and an 18-month application calendar."),
    # $19.99 — earlier in the same journey: prerequisites, GPA repair, timing.
    (r"crna-prereq|prerequisite|crna-school-cost|crna-gpa|science-gpa|crna-timeline|"
     r"icu-experience|crna-programs|crna-school|crna\b|nurse-anesthet",
     "qdubzb", "CRNA Prerequisite Planner",
     "Track the prerequisites, science GPA and ICU hours each program expects, "
     "on one planning sheet."),
    # $27 — for nurses leaving the bedside who are not going the CRNA route.
    (r"career-change|leave-bedside|beyond-the-bedside|non-bedside|nurse-career|career-pivot|"
     r"nursing-jobs|job-interview|resume|informatics|case-management|utilization-review|"
     r"infection-control|legal-nurse|nurse-educator|travel-nurse|per-diem",
     "mmscsu", "Beyond the Bedside — Nurse Career Pivot Kit",
     "Non-bedside nursing paths, what each one pays, and how to position your ICU "
     "experience for them."),
]

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
  <a href="{store}/l/{slug}" target="_blank" rel="noopener"
     style="display:inline-block;padding:9px 16px;background:#0057b8;color:#fff;text-decoration:none;border-radius:5px;font-size:14px;font-weight:600;">See what's on it &rarr;</a>
  <p style="margin:12px 0 0;font-size:12px;line-height:1.5;color:#6b7f94;">Study material for nurses. Created with AI assistance. Not medical advice, and not admissions, career or financial advice. Program requirements and deadlines vary &mdash; verify them with each program directly.</p>
</aside>
<!-- /{sentinel} -->
"""


def build(slug, name, line):
    return BLOCK.format(sentinel=SENTINEL, name=name, line=line, slug=slug, store=STORE)


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
    added = refreshed = unchanged = 0

    for path in sorted(glob.glob("*.html")):
        slug = path[:-5].lower()
        html = open(path, encoding="utf-8").read()

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
    print(f"\n  {unchanged:5d}  already correct (idempotent no-op)")
    print(f"  {skipped_nomatch:5d}  no matching product — deliberately left alone")
    print(f"  {skipped_noanchor:5d}  no <h2> anchor — skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
