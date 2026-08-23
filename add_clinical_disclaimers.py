#!/usr/bin/env python3
"""
add_clinical_disclaimers.py — ensure every clinical article carries the site's
educational-use disclaimer.

WHY THIS EXISTS
497 of the 510 clinical articles already carry a disclaimer. The 13 that did not were,
by coincidence or otherwise, among the most consequential topics on the site:

    rocuronium vs vecuronium          paralytics
    cisatracurium (Nimbex)            paralytic
    cisatracurium vs succinylcholine  paralytics
    fentanyl vs hydromorphone         opioids
    vasopressor guide / titration     pressors
    argatroban / bivalirudin (HIT)    anticoagulants
    milrinone vs dobutamine           inotropes
    ketamine for alcohol withdrawal   sedation
    phenobarbital                     sedation
    sepsis nursing guide              time-critical management

These are the drugs where a dosing error is not recoverable. The disclaimer does not make
the content safe, and it is not a substitute for the content being correct — but a page of
drug dosing aimed at bedside nurses should not be the one page that omits "verify doses
independently, follow facility policy".

The wording is the site's own most-used variant (47 pages), not something invented here.
It is placed where the other 497 place it: at the end of the article body, immediately
before the trailing injected blocks.

IDEMPOTENT: a page that already carries any disclaimer language is skipped.

USAGE
    python3 add_clinical_disclaimers.py --dry-run
    python3 add_clinical_disclaimers.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# Verbatim from the 47 pages that use this variant — the one that mentions pharmacy
# guidance and independent dose verification, which is the right fit for drug articles.
DISCLAIMER = (
    '<p style="font-size:0.85em;color:#888;font-style:italic">'
    "This article is general educational information for licensed clinicians and students, "
    "not medical advice or a substitute for your institution&#39;s protocols, pharmacy "
    "guidance, or a provider&#39;s orders. Always follow facility policy and verify doses "
    "independently.</p>"
)

# A page is "clinical" if its slug names a drug, a device, or bedside management.
#
# WIDENED 2026-08-23. The original list was written to catch 13 known-missing pages and it
# fit them exactly, which meant it had never been tested against a page it should catch and
# didn't. Removing the held-product block from 546 articles exposed the gap: 18 pages lost
# the only disclaimer language they carried, and the classifier declined ALL of them because
# none of their slugs happened to contain one of the seven original words — including
# `ecmo-nurse-guide`, `ed-sepsis-protocol-nurses`, `refractory-shock-second-line-agents` and
# `acls-bls-nurse-certification-guide`. A classifier fitted to the cases that produced it
# reports zero problems forever. The terms below are ordinary clinical subjects that should
# have been here from the start, not a patch shaped around those 18 filenames.
CLINICAL_SLUG = re.compile(
    r"icu-nurses|vasopressor|ventilator|drip|sedation|guide-icu|nursing-guide|"
    r"acls|\bbls\b|bls-nurse|ecmo|sepsis|shock|refractory|arrhythmi|intubat|extubat|"
    r"paralytic|vasoactive|crrt|hemodynamic|code-drug|procedure-log",
    re.I,
)

# Any of these means the page already discloses; do not add a second one.
HAS_DISCLAIMER = re.compile(
    r"not medical advice|educational purposes|educational (content|information)|consult your|"
    r"does not constitute medical|clinical judg|institutional protocol|verify with|per your facility",
    re.I,
)

# The article body ends where the first trailing injected block begins.
TRAILING_MARKERS = (
    "<!-- gumroad-cta",
    '<div id="related-articles"',
    "<!-- AFFILIATE-CTA",
    "<footer",
    "<!-- COOKIE CONSENT BANNER",
    "<!-- ICU Notebook",
    "</body>",
)


def insertion_point(text: str) -> int | None:
    """Index of the first trailing block, i.e. the end of the article body."""
    found = [p for p in (text.find(m) for m in TRAILING_MARKERS) if p != -1]
    return min(found) if found else None


def add_disclaimer(text: str) -> str | None:
    """Return the page with a disclaimer appended to the body, or None if not needed."""
    if HAS_DISCLAIMER.search(text):
        return None
    at = insertion_point(text)
    if at is None:
        return None
    return text[:at] + DISCLAIMER + "\n\n" + text[at:]


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(
        f for f in os.listdir(HERE) if f.endswith(".html") and CLINICAL_SLUG.search(f)
    )

    added = skipped = refused = 0
    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text = add_disclaimer(text)
        if new_text is None:
            skipped += 1
            continue

        added += 1
        print(f"  + {name}")
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            added -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}clinical pages: {len(files)} | "
          f"disclaimer added: {added} | already had one: {skipped} | refused: {refused}")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
