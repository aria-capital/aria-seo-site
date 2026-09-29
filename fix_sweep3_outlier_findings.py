#!/usr/bin/env python3
"""
fix_sweep3_outlier_findings.py — six figures that are the lone outlier against the site itself.

From the same 58-page read sweep as fix_sweep3_read_findings.py. These are the
"lone-outlier-vs-siblings" class: the site states the figure correctly on one or more other
pages, so the only question is which statement is the outlier, and that is answered by counting
rather than by clinical judgement.

THIS SCRIPT COUNTS DEPENDENTS BEFORE EDITING, because the last two repairs did not.

    67e198da fixed an aPTT value and left two clauses reasoning from the old one.
    The same commit fixed succinylcholine's onset to "30-60 sec" on critical-care-medications
    and left the rocuronium row below it saying "90 sec onset (comparable to succinylcholine)".

  Twice in one day, a correct single-substring edit created a fresh self-contradiction because
  nothing else on the page was checked for dependence on the value. So every edit below was
  preceded by grepping its own page for the figure and for claims resting on it, and the
  vasopressin entry changes THREE occurrences rather than one for exactly that reason — fixing
  only the table cell would have left the prose contradicting the table.

  EDITS therefore carries an explicit expected-count. A repair that silently edits a different
  number of places than its author believed is the failure mode this field exists to block.

1. VASOPRESSIN DOSE RANGE — vasopressor-titration-guide-icu-2026, 3 occurrences.

   The page states its own position twice and correctly:
       "Typical dose: Fixed at 0.03 to 0.04 units/min (not weight-based; not titrated)"
       "Do not exceed 0.06 units/min without strong justification"
   — typical 0.03-0.04, hard ceiling 0.06. But three other places print the CEILING as the
   routine range, including a table cell that calls it "(fixed)":
       "<td>0.03-0.06 units/min (fixed)</td>"
       "Vasopressin is added second (0.03-0.06 units/min)"
       "replacement doses (0.03-0.06 units/min) restore this deficit"
   Labelling a range "(fixed)" whose top is 50% above the page's own fixed dose is the clearest
   form of the error. Two advertised siblings agree with the page's prose, not its table:
   sepsis-nursing-guide "Fixed dose 0.03-0.04 units/min; do NOT titrate" and
   refractory-shock-second-line-agents "Fixed at 0.03-0.04 units/min IV. Do not titrate".
   The ">0.06 units/min (ischemia risk)" column and the "Do not exceed 0.06" sentence are
   CORRECT and are deliberately left alone: 0.06 is a real ceiling, just not a routine dose.

2. ROCURONIUM ONSET — critical-care-medications-nursing-guide-2026.

   "higher dose (1.2 mg/kg) -> 90 sec onset (comparable to succinylcholine for RSI)"

   Two siblings put the high-dose RSI onset at roughly 45-60 s: rocuronium-vs-succinylcholine
   ("intubating conditions in roughly 45-60 seconds when rocuronium is dosed at the higher RSI
   dose") and rocuronium-vs-vecuronium ("comparable intubating conditions in roughly 60
   seconds"). And the succinylcholine row immediately above on THIS page says "fastest onset
   (30-60 sec)", so "90 sec ... comparable to succinylcholine" contradicts its own table. The
   dose (1.2 mg/kg) is correct and unchanged.

3. LACTATE CLEARANCE INTERVAL — sepsis-protocol-2026.

   "A 10% or greater decrease per hour is a positive indicator of adequate resuscitation."

   Per HOUR demands roughly double what the site sets everywhere else. sepsis-nursing-guide
   states ">=10% per 2 hr" three times and septic-shock-nursing-guide agrees. This page's own
   repeat-lactate cadence is 2-hourly ("repeat in 2h if initial >2"), so the per-hour figure
   sits against its own protocol table.

4. MAGNESIUM DOSING BASIS — iv-magnesium-replacement-icu-2026.

   "typically 1-2 grams per gram of deficit given over an hour or more"

   A serum magnesium deficit is never expressed in grams — levels are mg/dL or mEq/L, and
   estimated total-body deficits are mEq/kg. "Per gram of deficit" names a denominator no nurse
   can compute. The 1-2 g itself is right and unchanged; only the basis is replaced, with the
   sibling's level-guided wording from magnesium-sulfate-guide-icu-nurses-2026 ("1-2 g IV per
   dose depending on the level and renal function").

5. CONCENTRATED KCl THRESHOLD — medication-error-prevention-nursing-2026.

   "Concentrated electrolytes | KCl >2 mEq/mL, hypertonic saline (3% NaCl), calcium chloride"

   The row's own rule is that these are banned from floor stock and never IV push. The product
   that rule exists for is the 2 mEq/mL concentrate — which a strict ">2 mEq/mL" threshold
   excludes. A safety rule whose threshold excludes the hazard it names is self-defeating. The
   sibling that states a threshold uses ">1 mEq/mL" and therefore captures it.

6. NORMAL ICP RANGE — neurological-assessment-nursing-guide-2026.

   "Normal ICP: 5-15 mmHg (7-20 in some sources)"

   The parenthetical conflates the TREATMENT threshold with the normal range: no source calls
   20 mmHg normal, and the next bullet on this page already says "Sustained ICP >20 mmHg =
   abnormal". Three siblings give 5-15 or ~7-15. The parenthetical is deleted rather than
   rewritten, which matches the TBI sibling verbatim and adds nothing.

WHAT IS DELIBERATELY NOT FIXED, from the same class
Five more lone-outlier candidates where BOTH figures are published and the difference is
protocol or definitional, not error. These stay with the owner:
  - epinephrine infusion 0.05-2 vs the sibling's 0.01-0.5 mcg/kg/min (full permissible range
    vs guideline-typical — a range-definition difference, not a wrong number)
  - hyponatremia severity bands, 5-10 mEq/L below the sibling's (a classification, and picking
    bands is clinical)
  - post-op bladder-scan threshold 400-500 vs the sibling's 300-400 mL (both published)
  - platelet infusion 15-30 vs 30-60 min (both taught)
  - PRBC start rate 25-50 mL/hr vs the sibling's 2 mL/min (protocol-dependent; slower is safe)

SCOPE AND SAFETY
Eight substring replacements across six files. Each entry declares how many occurrences it
expects; the script re-checks at run time and refuses any file where the count does not match.
No edit introduces a number absent from this site; two introduce no digit at all.

IDEMPOTENT: no replacement contains its own pattern.

USAGE
    python3 fix_sweep3_outlier_findings.py --dry-run
    python3 fix_sweep3_outlier_findings.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, expected_count, why, the page whose wording supplies the correction)
EDITS: list[tuple[str, str, str, int, str, str]] = [
    (
        "vasopressor-titration-guide-icu-2026.html",
        "0.03–0.06 units/min",
        "0.03–0.04 units/min",
        3,
        "the page's own prose says fixed 0.03-0.04; 0.06 is its stated ceiling, not a routine dose",
        "the same page ('Fixed at 0.03 to 0.04 units/min'), plus sepsis-nursing-guide and "
        "refractory-shock-second-line-agents",
    ),
    (
        "critical-care-medications-nursing-guide-2026.html",
        "(1.2 mg/kg) → 90 sec onset",
        "(1.2 mg/kg) → ~60 sec onset",
        1,
        "contradicts the succinylcholine row above it on this page (30-60 sec) and two siblings",
        "rocuronium-vs-vecuronium-icu-nurses-2026.html ('roughly 60 seconds')",
    ),
    (
        "sepsis-protocol-2026.html",
        "A 10% or greater decrease per hour",
        "A 10% or greater decrease per 2 hours",
        1,
        "the site sets lactate clearance at >=10% per 2 hr on two advertised pages, four times",
        "sepsis-nursing-guide-2026.html ('lactate clearance >=10% per 2 hr')",
    ),
    (
        "iv-magnesium-replacement-icu-2026.html",
        "1&ndash;2 grams per gram of deficit given over an hour or more",
        "1&ndash;2 g IV per dose depending on the level and renal function, given over an hour or more",
        1,
        "'per gram of deficit' names a denominator that does not exist; Mg is mg/dL or mEq/L",
        "magnesium-sulfate-guide-icu-nurses-2026.html ('1-2 g IV per dose depending on the "
        "level and renal function')",
    ),
    (
        "medication-error-prevention-nursing-2026.html",
        "KCl &gt;2 mEq/mL",
        "KCl &gt;1 mEq/mL",
        1,
        "a floor-stock ban whose threshold excludes the 2 mEq/mL concentrate it exists for",
        "medication-safety-high-alert-drugs-nursing-guide-2026.html ('KCl >1 mEq/mL concentrate')",
    ),
    (
        "neurological-assessment-nursing-guide-2026.html",
        "Normal ICP: 5–15 mmHg (7–20 in some sources)",
        "Normal ICP: 5–15 mmHg",
        1,
        "the parenthetical calls 20 mmHg normal; the next bullet calls sustained >20 abnormal",
        "traumatic-brain-injury-nursing-guide-2026.html ('Normal ICP: 5-15 mmHg'), verbatim",
    ),
]


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = skipped = 0

    for path, old, new, expected, why, source in EDITS:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            print(f"SKIP  {path}: file not found")
            skipped += 1
            continue

        count = text.count(old)
        if count != expected:
            # Refuse rather than guess. Editing a different number of places than the author
            # believed is exactly how a partial repair creates a fresh self-contradiction.
            print(f"SKIP  {path}: pattern occurs {count} times, expected exactly {expected}")
            print(f"      ({why})")
            skipped += 1
            continue

        updated = text.replace(old, new)
        if old in updated:
            print(f"SKIP  {path}: replacement still contains the pattern — refusing")
            skipped += 1
            continue

        print(f"{'[dry-run] ' if dry else ''}FIX   {path}  ({expected}x)")
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
