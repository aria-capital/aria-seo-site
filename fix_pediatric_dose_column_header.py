#!/usr/bin/env python3
"""
fix_pediatric_dose_column_header.py — a column header that mislabels three of its own rows.

WHY THIS EXISTS
pediatric-medication-dosing-guide-2026 carries a high-alert dosing table whose third column is
headed "Maximum Single Dose". Three of its seven rows do not hold a single dose:

    Acetaminophen (Tylenol)  | 10-15 mg/kg q4-6h        | 75 mg/kg/day (max 5 doses/24hr)
    Ibuprofen (Motrin)       | 5-10 mg/kg q6-8h         | 40 mg/kg/day; 400 mg/dose
    Ceftriaxone              | 50-100 mg/kg/day         | 4 g/day (meningitis); 2 g/day (other)
    Amoxicillin              | 40-90 mg/kg/day          | 500 mg/dose (standard)
    Morphine                 | 0.05-0.1 mg/kg q2-4h     | 0.1-0.15 mg/kg per dose
    Ondansetron (Zofran)     | 0.15 mg/kg IV            | 4 mg/dose (<40 kg); 8 mg/dose
    Dexamethasone            | 0.15-0.6 mg/kg           | 10 mg/dose for croup

NO NUMBER IN THE TABLE IS WRONG, and that is the whole point of the repair. Every cell labels
its own unit — "/day" or "/dose" — so the figures are correct and self-describing. The HEADER
is what is false: it asserts "single dose" over a column that is three-sevenths daily maxima.

HARM, stated at its real size rather than inflated. A reader scanning the column for a
single-dose ceiling reads acetaminophen's 75 mg/kg as one dose, which is 5-7x the 10-15 mg/kg
the same row gives as typical. The mitigation is that the cell says "/day" plainly, and says
"(max 5 doses/24hr)" beside it, so this is a misread available to a hurried scanner rather
than a wrong figure handed to a careful one. It is worth fixing anyway because the row's own
note reads "Most common OD in children from caregiver overdosing" — this is precisely the
table where a column-scan misread costs the most.

THE FIX IS A DELETION, NOT A REWRITE. "Maximum Single Dose" -> "Maximum Dose" removes the false
word and leaves every cell's own "/day" or "/dose" to carry the meaning. That is standing
priority 5 — prefer removing a false statement over adding a qualifying one — and it invents
no clinical content, proposes no new number, and needs no clinician to adjudicate. The
alternative repairs both fail that test: splitting the column into two would require supplying
single-dose maxima the site does not publish for acetaminophen or ceftriaxone, and appending
"(per dose or per day as noted)" adds copy rather than removing an untruth.

SCOPE NOTE — this page is LIVE BUT NOT ADVERTISED. It carries
<meta name="robots" content="noindex, follow">, so it is absent from sitemap.xml and search
engines are asked not to index it. Noindex means unadvertised, not unserved: a direct link,
an internal link or an old bookmark still reaches it. It sits in the 74-page noindex surface
that CLAUDE.md records as carrying ~300 dose lines that no audit has ever read, and it is the
first finding out of that surface.

SCOPE AND SAFETY
One exact substring in one file, verified to occur exactly once before this script was written;
the script re-checks at run time and refuses if the count is not 1.

IDEMPOTENT: the replacement does not contain the pattern.

USAGE
    python3 fix_pediatric_dose_column_header.py --dry-run
    python3 fix_pediatric_dose_column_header.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, what licenses the change)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "pediatric-medication-dosing-guide-2026.html",
        "<th>Maximum Single Dose</th>",
        "<th>Maximum Dose</th>",
        "3 of 7 rows hold a DAILY maximum, not a single dose",
        "deletion of a false word; every cell already labels itself /day or /dose",
    ),
]


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = skipped = 0

    for path, old, new, why, source in EDITS:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            print(f"SKIP  {path}: file not found")
            skipped += 1
            continue

        count = text.count(old)
        if count != 1:
            print(f"SKIP  {path}: pattern occurs {count} times, expected exactly 1")
            print(f"      ({why})")
            skipped += 1
            continue

        updated = text.replace(old, new)
        if old in updated:
            print(f"SKIP  {path}: replacement still contains the pattern — refusing")
            skipped += 1
            continue

        print(f"{'[dry-run] ' if dry else ''}FIX   {path}")
        print(f"      why:    {why}")
        print(f"      basis:  {source}")
        print(f"      -       {old}")
        print(f"      +       {new}")
        if not dry:
            safe_write_html(path, updated, allow_preexisting=True)
        changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}{changed} edit(s) applied, {skipped} skipped.")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
