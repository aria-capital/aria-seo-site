#!/usr/bin/env python3
"""
fix_arrest_amiodarone_dose.py — correct one arrest dose that contradicts the rest of the site.

WHY THIS EXISTS
`cardiac-dysrhythmia-nursing-guide-2026`'s "Key Drugs for Cardiac Rhythms" table printed:

    150 mg over 10 min for pulseless VT/VF; 150 mg over 10 min for stable VT

"150 mg over 10 minutes" is the STABLE VT regimen. In cardiac arrest the 2020 AHA algorithm
gives amiodarone 300 mg IV/IO as the first dose (150 mg for the second), pushed between
shocks — a 10-minute infusion cannot be delivered during CPR at all. The cell states the
indication itself ("for pulseless VT/VF"), so this is not shorthand: it assigns the
perfusing-rhythm regimen to the arrest pathway, and then repeats the same regimen for stable
VT in the next clause. The shape of it — the same dose and rate twice — is what a clobbered
clause looks like, not an alternate protocol.

WHY THIS IS NOT A SCRIPT INVENTING CLINICAL CONTENT
The corrected wording is the site's OWN, taken from pages that already state it correctly:
  acls-bls-nurse-certification-guide-2026 : "amiodarone (300mg IV/IO for VF/pulseless VT,
                                             150mg for stable VT)"  <- identical structure
  code-blue-nursing-guide-2026            : "Amiodarone 300 mg IV (then 150 mg for 2nd dose)"
  amiodarone-guide-icu-nurses-2026        : "300 then 150 in arrest, load-then-drip with a pulse"
"300 mg" appeared zero times in the offending file, so this page was the lone outlier in the
corpus. The repair makes it consistent with the publisher's own standard.

VERIFICATION BEFORE THE EDIT
Found by a drug-class dose audit and then put to three independent skeptics, each instructed
to refute it and to default to "refuted" when uncertain. All three failed to refute and each
confirmed the quote verbatim (3/3). Their decisive argument was the corpus-internal one
above: house style cannot excuse a value the house contradicts three times.

SCOPE
Exactly one substring, in one file. The stable-VT clause is correct and is left alone — only
the arrest clause changes. If the pattern does not match (already fixed, or reworded), the
script reports and changes nothing.

IDEMPOTENT: the pattern cannot match its own output.

USAGE
    python3 fix_arrest_amiodarone_dose.py --dry-run
    python3 fix_arrest_amiodarone_dose.py
"""

from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

from safe_write import safe_write_html

# Anchored on the arrest indication so it can only ever touch the pulseless clause. The
# stable-VT clause that follows shares the same dose text and must survive untouched.
ARREST = re.compile(r"(?i)\b150\s*mg\s+over\s+10\s*min(?:utes)?\s+for\s+pulseless\s+VT\s*/\s*VF")
REPLACEMENT = "300 mg IV/IO push for pulseless VT/VF (150 mg for a second dose)"


def correct(html: str) -> tuple[str, int]:
    """Return (new_html, n_changed)."""
    return ARREST.subn(REPLACEMENT, html)


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = 0
    for path in sorted(glob.glob("*.html")):
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        if "amiodarone" not in html.lower():
            continue
        new, n = correct(html)
        if not n:
            continue
        print(f"  {'would fix' if dry else 'fixed'} {n}x  {path}")
        if not dry:
            safe_write_html(path, new, allow_preexisting=True)
        changed += 1
    print(f"\n{'[dry-run] ' if dry else ''}{changed} file(s) corrected.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
