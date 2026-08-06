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
RULES = [
    (r"ecg|ekg|12-lead|twelve-lead|rhythm|telemetry|arrhythmia|dysrhythmia|atrial-fib|svt|v-?tach",
     "wyjmqr", "12-Lead ECG Quick-Read Card",
     "A step-by-step order for reading any strip, on one fold-up card."),
    # (^|-) on epinephrine so "norepinephrine" does NOT match here — it is a titrated drip,
    # not a code-cart push, and it belongs to the infusions card below. Caught by a test.
    (r"acls|code-blue|code-cart|cardiac-arrest|resuscitat|(^|-)epinephrine|amiodarone|defibrillat",
     "kvppg", "ACLS Code Drug Pocket Card (2026)",
     "Every code-cart drug on one fold-up reference."),
    (r"abg|blood-gas|acid-base|acidosis|alkalosis|ventilat|intubat|extubat|oxygenat|respiratory-failure|ards",
     "avsrc", "ICU ABG Interpretation Quick Guide",
     "Work through a blood gas in a fixed order instead of from memory."),
    (r"pressor|vasopressor|infusion|drip|titrat|norepinephrine|levophed|sepsis|septic|shock|hemodynamic",
     "bvezxw", "Critical-Care Infusions Pocket Card",
     "The infusions you titrate at the bedside, collected on one card."),
    (r"crrt|dialysis|prone|ecmo|arterial-line|a-line|swan|procedure|bedside-procedure",
     "ubwher", "ICU Critical Care Procedures Quick Reference",
     "CRRT, proning, ECMO and arterial lines in one place."),
    (r"wound|ostomy|drain|catheter|central-line|picc|foley|chest-tube|tracheostomy|feeding-tube|device",
     "itikqo", "ICU Bedside Devices & Lines Quick Reference",
     "The lines, tubes and devices at the bedside, one reference."),
    (r"abdominal|gi-bleed|pancreatit|liver|hepatic|bowel|gastro|ileus|obstruction",
     "dpdvwf", "ICU Abdominal Emergencies Quick Reference",
     "The abdominal emergencies that escalate fastest."),
    (r"ccrn|certification|cert-exam|critical-care-exam",
     "oolhqk", "CCRN Blueprint Study Guide",
     "Organized around the CCRN blueprint, domain by domain."),
    # Broad clinical fallback — only for genuinely ICU/critical-care articles.
    (r"\bicu\b|intensive-care|critical-care|criticalcare",
     "qaebvo", "The ICU Notebook",
     "Bedside references built for ICU shifts."),
]

BLOCK = """<!-- {sentinel} -->
<aside style="border:1px solid #d7e3f4;border-left:4px solid #0057b8;background:#f7fafd;border-radius:6px;padding:18px 20px;margin:28px 0;">
  <p style="margin:0 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#5b7a9d;">From The ICU Notebook</p>
  <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#0d2a45;">{name}</p>
  <p style="margin:0 0 12px;font-size:14px;line-height:1.5;color:#41576e;">{line}</p>
  <a href="{store}/l/{slug}" target="_blank" rel="noopener"
     style="display:inline-block;padding:9px 16px;background:#0057b8;color:#fff;text-decoration:none;border-radius:5px;font-size:14px;font-weight:600;">See what's on it &rarr;</a>
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


def main():
    apply_changes = "--apply" in sys.argv
    if not apply_changes and "--dry-run" not in sys.argv:
        print("pass --dry-run or --apply")
        return 2

    counts, skipped_nomatch, skipped_done, skipped_noanchor, written = {}, 0, 0, 0, 0

    for path in sorted(glob.glob("*.html")):
        slug = path[:-5].lower()
        html = open(path, encoding="utf-8").read()

        if SENTINEL in html:
            skipped_done += 1
            continue

        hit = match(slug)
        if not hit:
            skipped_nomatch += 1
            continue
        permalink, name, line = hit

        # Insert above the first <h2 — after the headline and intro, high on the page.
        anchor = re.search(r"<h2[\s>]", html)
        if not anchor:
            skipped_noanchor += 1
            continue

        at = anchor.start()
        new = html[:at] + build(permalink, name, line) + html[at:]

        counts[name] = counts.get(name, 0) + 1
        written += 1
        if apply_changes:
            # Repo rule 1: never raw open(...,'w') on an article. This is a bulk edit
            # of pre-existing files, so allow_preexisting=True — refuse only on regression.
            safe_write_html(path, new, allow_preexisting=True)

    print(("APPLIED" if apply_changes else "DRY RUN") + f" — {written} article(s) matched\n")
    for name in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {counts[name]:5d}  {name}")
    print(f"\n  {skipped_nomatch:5d}  no matching product — deliberately left alone")
    print(f"  {skipped_done:5d}  already had a CTA (idempotent skip)")
    print(f"  {skipped_noanchor:5d}  no <h2> anchor — skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
