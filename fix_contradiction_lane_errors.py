#!/usr/bin/env python3
"""
fix_contradiction_lane_errors.py — two figures the site contradicts on its own dedicated pages.

WHY THIS EXISTS
Found by the cross-page contradiction lane: 48 high-alert drugs, each compared across every
advertised page that names it with a number, hunting for the site disagreeing with ITSELF.
That lane had never run before 2026-09-28 — a session rate limit killed it twice — and it is
the same lane that found the amiodarone arrest-dose error.

Both edits below were raised INDEPENDENTLY BY TWO LANES that could not see each other's work,
and both were then confirmed by direct measurement against the corpus, not taken on an agent's
word. Neither introduces a number that was not already published on this site.

1. FOSPHENYTOIN MAX RATE — phenytoin's ceiling printed as fosphenytoin's.

   iv-push-medication-safety-icu-nurses-2026 printed:
       No faster than 50 mg PE/min (fosphenytoin); 50 mg/min (phenytoin)

   Both drugs given the same ceiling. The site's own dedicated comparison page
   (phenytoin-fosphenytoin-guide-icu-nurses-2026, line 90) is a two-column table row reading:

       Max infusion rate | 50 mg/min | 150 mg PE/min
                           phenytoin   fosphenytoin

   and seizure-nursing-guide-2026 states 150 mg PE/min twice more. Three instances across two
   pages agree; this page is the lone outlier. The same dedicated page explains WHY the
   difference exists — "Fosphenytoin can be given faster and with less local and cardiovascular
   irritation, which is a major reason it's often preferred for loading" — so the 150 figure is
   not incidental to this site, it is the point the site makes about the drug.

   HARM: a 20 mg PE/kg status-epilepticus load in a 70 kg adult is 1,400 mg PE. At 50 mg PE/min
   that is ~28 minutes; at the site's own 150 mg PE/min it is ~10. Eighteen extra minutes of
   seizing while the nurse follows the page.

   FIX: 150 mg PE/min for fosphenytoin. The phenytoin clause in the same cell is correct
   (50 mg/min IS phenytoin's ceiling) and is deliberately left untouched.

2. MAGNESIUM TOXICITY THRESHOLDS — mEq/L values printed under a mg/dL label.

   fluid-electrolytes-nursing-guide-2026 declares "Magnesium (Normal: 1.5–2.5 mg/dL)" and then
   printed:
       Mg &gt;7: respiratory arrest; Mg &gt;12: cardiac arrest

   Read in the page's own declared unit, >7 mg/dL is about >5.8 mEq/L — which sits INSIDE the
   band this site publishes on preeclampsia-hellp-nursing-guide-2026 as
   "4–7 mEq/L | THERAPEUTIC RANGE — seizure prophylaxis | Continue infusion".

   HARM: a nurse running eclampsia seizure prophylaxis sees a therapeutic level — DTRs present,
   respirations normal — consults this page, and reads it as respiratory arrest territory.
   The error runs toward stopping a needed infusion, and it mislabels the actual danger zone.

   FIX: the four-band sequence this site already publishes, with the unit made explicit so the
   numbers can no longer be read against the mg/dL label above them:
       10–13 mEq/L  respiratory depression      ->  "Mg &gt;10 mEq/L: respiratory depression"
       >15 mEq/L    cardiac arrest              ->  "Mg &gt;15 mEq/L: cardiac arrest"

   NOT FIXED HERE, deliberately: the same page's "Normal: 1.5–2.5 mg/dL" is itself the mEq/L
   range wearing a mg/dL label (this site prints 1.7–2.2 mg/dL elsewhere). That is a separate,
   lower-confidence finding about a reference range rather than a toxicity threshold, and
   correcting it means choosing which of two published ranges the page should carry — a call
   for the owner, not a script. Making the toxicity units explicit is what removes the harm.

WHAT THIS DOES NOT CLAIM
Two findings from the same lane sweep are NOT included, because they need a number this site
does not publish or a judgement it does not make: the CRRT citrate-toxicity sentence naming
metabolic alkalosis where accumulation produces acidosis, and an alcohol-withdrawal escalation
trigger of "40–60 mg lorazepam in 1 hour" that is 10–30x the same page's own PRN ceiling. Both
are recorded for the owner rather than edited.

SCOPE AND SAFETY
Two exact substrings in two files. Each was checked to occur EXACTLY ONCE before this script
was written; the script re-checks at run time and refuses any file where the count is not 1.
No regex, no fuzzy matching.

IDEMPOTENT: neither replacement contains its own pattern.

USAGE
    python3 fix_contradiction_lane_errors.py --dry-run
    python3 fix_contradiction_lane_errors.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, the page whose wording supplies the correction)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "iv-push-medication-safety-icu-nurses-2026.html",
        "No faster than 50 mg PE/min (fosphenytoin); 50 mg/min (phenytoin)",
        "No faster than 150 mg PE/min (fosphenytoin); 50 mg/min (phenytoin)",
        "phenytoin's ceiling printed as fosphenytoin's; adds ~18 min to a status epilepticus load",
        "phenytoin-fosphenytoin-guide-icu-nurses-2026.html (Max infusion rate row: 150 mg PE/min)",
    ),
    (
        "fluid-electrolytes-nursing-guide-2026.html",
        "Mg &gt;7: respiratory arrest; Mg &gt;12: cardiac arrest",
        "Mg &gt;10 mEq/L: respiratory depression; Mg &gt;15 mEq/L: cardiac arrest",
        "mEq/L values under a mg/dL label: >7 mg/dL is inside this site's own therapeutic band",
        "preeclampsia-hellp-nursing-guide-2026.html (10-13 mEq/L respiratory depression; >15 arrest)",
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
            # Refuse rather than guess. A reworded target means a human should look, and a
            # silent no-op is how a repair pretends to have run.
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
