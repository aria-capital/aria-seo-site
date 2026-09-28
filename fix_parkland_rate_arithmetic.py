#!/usr/bin/env python3
"""
fix_parkland_rate_arithmetic.py — one worked example whose own numbers refute it.

WHY THIS EXISTS
Found 2026-09-28 by the completeness critic of the second clinical sweep, on its FIRST contact
with a page no dose lane had ever inventoried. It is the cheapest class of error this site can
have and the only one that needs no clinical judgement at all: the page states the inputs, and
the inputs give a different answer than the page prints.

burns-nursing-guide-2026, Parkland formula worked example, verbatim:

    Total = 4 x 70 x 40 = 11,200 mL (11.2 L)
    First 8 hr: 5,600 mL (720 mL/hr)
    Next 16 hr: 5,600 mL (350 mL/hr)

Every figure there is right except one. 4 x 70 x 40 = 11,200. Half of 11,200 is 5,600.
5,600 / 16 = 350, as printed. But 5,600 / 8 = **700**, not 720.

There is no reading under which 720 is correct. It is not a delayed-arrival adjustment
(arrival at 1 h post-burn would give 5,600/7 = 800); 5,600/720 is 7.78 hours, which is not a
number the page or the formula ever names. It is an arithmetic slip.

WHY THE CORRECTION NEEDS NO EXTERNAL SOURCE
This is the one repair class where "propagate the publisher's own wording" is not even
required: the page supplies both operands. 700 is derived from the page's own 5,600 mL and its
own 8 hours. Nothing is invented, nothing is borrowed from a sibling, and no clinician has to
choose between two published conventions. Contrast the IV potassium items, which were left for
the owner precisely because the right value was a protocol-dependent range.

HARM
Low, and stated honestly rather than inflated. 720 vs 700 mL/hr is a 2.9% error, well inside
the titration range that urine output drives anyway — the same page says to titrate to
0.5-1 mL/kg/hr. The real cost is to trust: this is a page TEACHING the formula, so a nurse
checking their own correct arithmetic against it concludes they are wrong. A worked example
that does not work is worse than no worked example.

WHAT WAS MEASURED, AND THE SHAPE THAT WAS REJECTED
Corpus-wide, before writing this. Two checks were run over all 1,462 pages:

  volume-over-hours ("first N hr: V mL (R mL/hr)"): 2 instances, both on this page, 1 wrong.
      The correct one (5,600 mL / 16 hr = 350) is a built-in negative control - it proves the
      checker discriminates rather than firing on the shape.

  chained multiplication ("a x b x c = d"): 11 instances, 9 correct and 2 apparent failures,
      and BOTH apparent failures were the checker's fault:
        - "3x12 = 3 days worked"  (icu-nurse-shift-length) - the '3' is the start of a phrase,
          not the product.
        - "293/250 x 5 = 5.9"  (pediatric-medication-dosing) - correct; the regex dropped the
          leading division.
      A 2-in-11 false-positive rate on healthy pages is a guard that gets trained away within
      a week, so that shape is deliberately NOT shipped as a test. This repo has already paid
      for that lesson once: a guard whose needle was a substring of the right answer
      ("50 mg PE/min" inside "150 mg PE/min") reddened the two pages that were correct.
      Only the shape with a measured clean run is guarded, in tests/test_fix_parkland_rate_arithmetic.py.

SCOPE AND SAFETY
One exact substring in one file, verified to occur exactly once before this script was written;
the script re-checks at run time and refuses if the count is not 1. No regex, no fuzzy matching.

IDEMPOTENT: the replacement does not contain the pattern.

USAGE
    python3 fix_parkland_rate_arithmetic.py --dry-run
    python3 fix_parkland_rate_arithmetic.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, where the corrected number comes from)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "burns-nursing-guide-2026.html",
        "First 8 hr: 5,600 mL (720 mL/hr)",
        "First 8 hr: 5,600 mL (700 mL/hr)",
        "5,600 mL over 8 hr is 700 mL/hr; the example printed 720",
        "the page's own figures (5,600 mL and 8 hours) - nothing borrowed, nothing invented",
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
            # Refuse rather than guess. A silent no-op is how a repair pretends to have run.
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
        print(f"      source: {source}")
        print(f"      -       {old}")
        print(f"      +       {new}")
        if not dry:
            safe_write_html(path, updated, allow_preexisting=True)
        changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}{changed} edit(s) applied, {skipped} skipped.")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
