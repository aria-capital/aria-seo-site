#!/usr/bin/env python3
"""
fix_sweep3_read_findings.py — five findings from reading the 58 pages nobody had ever read.

WHY THIS EXISTS
The 2026-09-28 completeness critic established that 47 advertised dose-bearing pages had never
been read end to end by anything, and that the 118-page inventory those passes measured
coverage against had itself dropped 16 more advertised pages. Reading all 58 produced 1,351
examined dose expressions and 30 candidates. These are the five the site itself settles.

THE FIRST TWO ARE MY OWN HALF-FINISHED REPAIR, and that is the most useful thing in this file.

    commit 67e198da (earlier today) corrected the SBAR Background of
    nursing-handoff-shift-report-guide-2026 from "Last PTT at 1400 was 78 - sub-therapeutic"
    to "78 - therapeutic", because 78 s sits inside the 60-100 s therapeutic range this site
    publishes on five pages.

    It did not touch the two clauses that REASON from that value, six and nine lines below:

        Assessment:     "...demand ischemia given the sub-therapeutic PTT and his reduced EF"
        Recommendation: "...adjust the heparin drip if it's STILL sub-therapeutic"

    So a repair that fixed one wrong word left the page contradicting itself inside one SBAR
    script. The residual clauses argue for increasing a heparin rate that is already in range.

  The generalizable lesson, which is why it is written here rather than quietly patched:
  A SINGLE-SUBSTRING REPAIR IS THE RIGHT TOOL FOR A WRONG VALUE AND THE WRONG TOOL FOR A WRONG
  BELIEF. When a page reasons from a figure, correcting the figure leaves every inference drawn
  from it standing. Before an exact-substring fix, grep the page for what else depends on the
  thing being changed - here, one grep for "therapeutic" would have shown all three clauses.
  This is the sibling lesson turned inward: the same defect was not searched for within the
  same file.

  Both fixes are deletions that complete the choice 67e198da already made. The alternative -
  restoring the scenario's original intent by making 78 a genuinely sub-therapeutic number -
  would mean inventing a lab value and re-breaking the range agreement across five pages.

3. PYRIDOXINE "KILOGRAM-SCALE" - isoniazid-toxicity-icu-nurses-2026.

   "many pharmacies don't stock kilogram-scale pyridoxine"

   Three orders of magnitude out, and the page refutes it itself: "gram-for-gram" appears
   EIGHT times, "in grams" twice, including the pull-quote "Give the vitamin like a drug, in
   grams", and the empiric dose is ~5 g IV. IV pyridoxine comes as 100 mg/mL vials, so a 5 g
   dose is 50 mL - the real logistics problem is assembling dozens of vials of a gram-scale
   dose. Replaced with the page's own word. Lone outlier, 1 against 10.

4. FUROSEMIDE WORKED EXAMPLE - heart-failure-nursing-guide-2026, arithmetic.

   "IV dose should be >= patient's home oral dose x 2.5 (e.g., home 40 mg PO daily
    -> give 80-100 mg IV)"

   40 x 2.5 = 100. The example's lower bound of 80 mg is 2.0x, so the page's own worked example
   does not satisfy the rule stated in the same sentence. Same class as the Parkland fix: the
   page supplies the multiplier and the operand, so the correction is derived from its own
   numbers and nothing is invented. 80 mg is not a dangerous dose - the defect is that a page
   teaching a rule immediately breaks it, and a nurse checking their own correct arithmetic
   against it concludes they are wrong.

5. PLATELET COUNT INCREMENT - blood-transfusion-nursing-guide-2026, read row-wise.

   The Blood Product table's Platelets row defines a unit in its Volume cell as
   "~50-70 mL per unit (apheresis single donor ~200-300 mL)" - a whole-blood-derived unit -
   and then its Expected Effect cell says "Expected rise of 30,000-50,000/uL PER UNIT".

   One row, two meanings of "per unit". The site's own dedicated page is explicit:
   platelet-transfusion-icu-nurses-2026 - "One apheresis unit (equivalent to a pool of
   whole-blood-derived platelets) typically raises an adult's count by roughly 30 to 50 x
   10^9/L". A single random-donor unit raises far less. The qualifier is propagated verbatim
   from that page; no number changes. This one is only visible reading the row under its column
   headers, which is exactly the heading-attributed shape the critic said every past miss had.

WHAT IS NOT HERE
Twenty-five other candidates from the same sweep, most classed
"single-source-external-reference-required" - the site states the figure once and nothing on
it can adjudicate. Those are recorded for the owner rather than guessed at.

SCOPE AND SAFETY
Five exact substrings in four files, each verified to occur EXACTLY ONCE before this script was
written; the script re-checks at run time and refuses any file where the count is not 1.
No edit introduces a number absent from this site; three introduce no digit at all.

IDEMPOTENT: no replacement contains its own pattern.

USAGE
    python3 fix_sweep3_read_findings.py --dry-run
    python3 fix_sweep3_read_findings.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, what supplies the correction)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "nursing-handoff-shift-report-guide-2026.html",
        "given the sub-therapeutic PTT and his reduced EF",
        "given his reduced EF",
        "residual of 67e198da: the Background now says 78 is therapeutic; this clause still is not",
        "deletion; completes the correction already made on the same page",
    ),
    (
        "nursing-handoff-shift-report-guide-2026.html",
        "still sub-therapeutic",
        "sub-therapeutic",
        "'still' asserts the last PTT was sub-therapeutic, which the same page now denies",
        "deletion of one word; the plain conditional is consistent with a therapeutic value",
    ),
    (
        "isoniazid-toxicity-icu-nurses-2026.html",
        "kilogram-scale pyridoxine",
        "gram-scale pyridoxine",
        "1000x overstatement; this page says gram-for-gram 8 times and 'in grams' twice",
        "the same page ('Give the vitamin like a drug, in grams'; empiric ~5 g IV)",
    ),
    (
        "heart-failure-nursing-guide-2026.html",
        "give 80–100 mg IV",
        "give 100 mg IV",
        "the example's 80 mg lower bound is 2.0x home dose, breaking the page's own '>= x 2.5' rule",
        "the page's own multiplier and operand (40 mg x 2.5 = 100)",
    ),
    (
        "blood-transfusion-nursing-guide-2026.html",
        "Expected rise of 30,000–50,000/uL per unit in non-refractory patient",
        "Expected rise of 30,000–50,000/uL per apheresis unit (equivalent to a pool of "
        "whole-blood-derived platelets) in non-refractory patient",
        "the row's Volume cell defines a unit as 50-70 mL; the 30-50k rise is per apheresis unit",
        "platelet-transfusion-icu-nurses-2026.html, qualifier propagated verbatim",
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
