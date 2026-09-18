#!/usr/bin/env python3
"""
Remove two inverted IV-potassium statements that are live on advertised pages.

WHAT IS WRONG, and why this deletes rather than corrects
--------------------------------------------------------
Both statements name a PERIPHERAL limit that is higher than the CENTRAL limit
they sit beside. Central access exists precisely so that potassium can be given
faster and more concentrated than a peripheral vein tolerates, so "peripheral
above central" is not a debatable protocol variant — it is backwards, and it is
backwards in the direction that invites harm.

  fluid-electrolyte-balance-nursing-guide-2026
      "Maximum concentration via peripheral IV: 40 mEq/100 mL.
       Maximum concentration via central line: up to 20 mEq/100 mL."
      Peripheral named as TWICE the central maximum. 40 mEq/100 mL is 400 mEq/L,
      a central, critical-care concentration. This site says exactly that, in
      those words, on the neighbouring page fluid-electrolytes-nursing-guide-2026:
      "40 mEq/100 mL is a central, critical-care concentration, never peripheral."

  diabetic-ketoacidosis-nursing-guide-2026
      "Replace K+ first (40 mEq/hr max peripherally; >10 mEq/hr central)."
      Caps a peripheral line at four times the rate it simultaneously names as
      central territory.

This script REMOVES the offending clauses and substitutes no number. That is
deliberate, and it is the repo's own standing priority 5: prefer removing a
false statement over adding a qualifying one, because removing an untrue claim
cannot create new exposure while choosing a replacement figure is clinical
judgement that belongs to the owner, who is the RN.

What survives each edit is correct and self-sufficient:

  fluid-electrolyte-balance: keeps "Never give IV potassium undiluted", keeps
      "Maximum peripheral IV rate: 10 mEq/hour (faster rates require cardiac
      monitoring and central line access)" — which is correct — and keeps
      "Verify rate and concentration against facility policy before infusing."
      The reader is still told to check the protocol; they are no longer told a
      wrong number first.

  DKA: becomes "HOLD insulin. Replace K+ first. Recheck before starting insulin."
      which is the standard sequence and is what the row is actually for.

Idempotent: re-running changes nothing, because the search strings are gone
after the first pass. Writes through safe_write_html(allow_preexisting=True)
per repo rule 2. --dry-run writes nothing.

Usage:
    python3 fix_inverted_potassium.py --dry-run
    python3 fix_inverted_potassium.py --apply
"""
from __future__ import annotations

import argparse
import sys

from safe_write import safe_write_html

# (path, exact substring to remove, short label)
# Each `find` is matched EXACTLY and must appear exactly once. If a page has been
# edited since this was written, the count check below refuses rather than guessing.
EDITS = [
    (
        "fluid-electrolyte-balance-nursing-guide-2026.html",
        " Maximum concentration via peripheral IV: 40 mEq/100 mL."
        " Maximum concentration via central line: up to 20 mEq/100 mL.",
        "",
        "inverted peripheral/central concentration pair",
    ),
    (
        "diabetic-ketoacidosis-nursing-guide-2026.html",
        "Replace K+ first (40 mEq/hr max peripherally; &gt;10 mEq/hr central).",
        "Replace K+ first.",
        "inverted peripheral/central rate",
    ),
]


def run(apply_changes: bool) -> int:
    changed = 0
    already = 0
    problems = []

    for path, find, replace, label in EDITS:
        try:
            src = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            problems.append(f"{path}: file not found")
            continue

        n = src.count(find)
        if n == 0:
            # Either already fixed, or the page changed under us. Tell them apart:
            # the wrong figures should be gone entirely, not merely reworded.
            if "40 mEq/100 mL" in src and "peripheral" in src:
                problems.append(
                    f"{path}: target string absent BUT '40 mEq/100 mL' still present "
                    f"near 'peripheral' — the page changed; re-read it by hand"
                )
            else:
                already += 1
                print(f"  ok (already clean)  {path}  [{label}]")
            continue

        if n > 1:
            problems.append(f"{path}: target string appears {n} times, expected 1 — refusing")
            continue

        new = src.replace(find, replace)
        if new == src:
            problems.append(f"{path}: replacement produced no change — refusing")
            continue

        print(f"  {'WOULD FIX' if not apply_changes else 'FIXED'}      {path}  [{label}]")
        print(f"      - {find.strip()}")
        print(f"      + {replace.strip() or '(removed)'}")
        if apply_changes:
            safe_write_html(path, new, allow_preexisting=True)
        changed += 1

    print()
    print(f"pages needing the fix: {changed} | already clean: {already} | problems: {len(problems)}")
    for p in problems:
        print(f"  PROBLEM: {p}")

    if problems:
        return 2
    if changed and not apply_changes:
        return 1  # dry run found work to do
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    g.add_argument("--apply", action="store_true", help="write the changes")
    args = ap.parse_args()

    print("Inverted IV-potassium statements — removal, no substitution\n")
    return run(apply_changes=args.apply)


if __name__ == "__main__":
    sys.exit(main())
