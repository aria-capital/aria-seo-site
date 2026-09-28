#!/usr/bin/env python3
"""
fix_sibling_completion_errors.py — two pages the site's own other pages already correct.

WHY THIS EXISTS
Both were surfaced by the 2026-09-28 sweep and both were initially SET ASIDE as "owner's call",
which was the wrong read in each case. They were re-examined and they are not judgement calls:
in both, the publisher has already stated the right thing — once on two sibling pages, once
five times on the offending page itself — and the defect is that one spot disagrees. That is
the same shape as the amiodarone arrest-dose repair, which is this repo's template for the
class: propagate the publisher's own wording, invent nothing.

Recording the initial misclassification on purpose. "Needs a clinician" is the correct call
when the right value is a protocol-dependent range (the IV potassium items, the sodium
correction ceiling). It is the WRONG call when the site has already chosen, because then the
only question is which of two statements by the same publisher is the outlier — and that is
answerable by counting, not by clinical judgement. Two findings nearly died of the right
caution applied to the wrong category.

1. LIDOCAINE REPEAT BOLUS — a repeat dose that reads as the full dose.

   amiodarone-vs-lidocaine-icu-nurses-2026, arrest section, verbatim:
       Lidocaine is a reasonable substitute when amiodarone isn't available or the team
       prefers it, dosed at 1-1.5 mg/kg with repeat boluses.

   Read literally, "repeat boluses" after "1-1.5 mg/kg" repeats 1-1.5 mg/kg. The repeat dose is
   half that. The site states the correct figure on two other pages and neither "0.75" nor the
   "~3 mg/kg" cumulative ceiling appears anywhere on the offending page:

       lidocaine-drip-guide-icu-nurses-2026:  "1-1.5 mg/kg IV push (may repeat 0.5-0.75 mg/kg)"
                                              max total loading: "~3 mg/kg"
       code-blue-nursing-guide-2026:          "May repeat 0.5-0.75 mg/kg q5-10 min"

   The strongest argument is on the offending page itself. Two paragraphs above the dosing, it
   warns: "toxic levels cause CNS effects - perioral numbness, confusion, seizures." The page
   names the hazard and then prints dosing that invites it.

   HARM: repeating 1-1.5 mg/kg instead of 0.5-0.75 mg/kg is roughly double, per repeat, during
   a cardiac arrest, of a drug whose toxicity is seizures and cardiovascular collapse.

   FIX: the drip guide's wording, verbatim. Only the repeat dose is added; the cumulative
   ceiling is a second statement and adding it would be widening rather than repairing.

2. DKA INSULIN-HOLD THRESHOLD — a protocol box that contradicts its own next line.

   diabetes-dka-hhs-nursing-guide-2026, consecutive list items:
       K+ <3.3 mEq/L: HOLD insulin; replace potassium aggressively (20-40 mEq/hr IV)
                      until K+ >=3.5, THEN start insulin
       K+ 3.3-5.0:    start insulin; add K+ to IV fluids (20-40 mEq per liter)

   One line says insulin resumes at 3.5; the line directly beneath it says insulin starts at
   3.3. A nurse reading the box cannot tell which applies at K+ 3.4.

   This is NOT the site picking the wrong published threshold. Both 3.3 (ADA) and 3.5 (many
   institutional protocols) are published, and an earlier adversarial pass correctly REFUTED a
   claim that 3.3 was wrong. The defect is narrower and is settled by counting: this page uses
   3.3 as its insulin threshold FIVE times -

       "K+ <3.3 mEq/L:" (the hold row) | "K+ 3.3-5.0: start insulin"
       "start at 0.1 units/kg/hr (after K+ >=3.3)" | "hold if K+ <3.3" | "K+ <3.3:"

   - and 3.5 exactly once, in this clause. The page has already chosen; one spot did not get
   the memo. Changing the outlier to the page's own figure resolves the contradiction without
   anyone choosing between two published conventions, which is precisely why this is safe to
   do and the sodium-correction ceiling (8-10 vs 8-12 vs 10-12 across four pages, no majority)
   is not.

   HARM: modest and in the delaying direction - insulin withheld between 3.3 and 3.5 - but the
   contradiction itself is the hazard, in a protocol box a nurse reads under time pressure.

   NOT CHANGED, deliberately: "20-40 mEq/hr IV" in the same sentence. That rate was flagged in
   an earlier pass and the adversarial review REFUTED it - 20-40 mEq/hr is published for this
   exact indication (K+ <3.3 in DKA, central access, continuous ECG). Correcting a figure that
   survived refutation would be re-introducing an error.

WHAT IS STILL LEFT FOR THE OWNER, and why these two are different
Three findings from the same sweep are NOT here because the site does not settle them:
  - hepatorenal albumin 1 g/kg/day: the maintenance figure appears nowhere on the site.
  - naloxone titration dilution: the conventional volume appears nowhere on the site.
  - 3% saline central-vs-peripheral: the site is split 3 pages to 2 and the stricter wording
    is a defensible institutional policy, not an error.
  - sodium correction ceiling: 8-10, 8-12 and 10-12 mEq/L/24h across four advertised pages
    with no majority. Same three near-identically-named sibling pages as the potassium errors.

SCOPE AND SAFETY
Two exact substrings in two files. Each verified to occur EXACTLY ONCE before this script was
written; the script re-checks at run time and refuses any file where the count is not 1.
No regex, no fuzzy matching. Neither replacement introduces a number that this site does not
already publish.

IDEMPOTENT: neither replacement contains its own pattern.

USAGE
    python3 fix_sibling_completion_errors.py --dry-run
    python3 fix_sibling_completion_errors.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, the page whose wording supplies the correction)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "amiodarone-vs-lidocaine-icu-nurses-2026.html",
        "dosed at 1&ndash;1.5&nbsp;mg/kg with repeat boluses",
        "dosed at 1&ndash;1.5&nbsp;mg/kg, with repeat boluses of 0.5&ndash;0.75&nbsp;mg/kg",
        "'repeat boluses' after the loading dose reads as repeating the FULL dose; the repeat is half",
        "lidocaine-drip-guide-icu-nurses-2026.html ('may repeat 0.5-0.75 mg/kg') and code-blue-nursing-guide-2026.html",
    ),
    (
        "diabetes-dka-hhs-nursing-guide-2026.html",
        "until K+ ≥3.5, THEN start insulin",
        "until K+ ≥3.3, THEN start insulin",
        "the next list item says insulin starts at 3.3; this page uses 3.3 five times and 3.5 once",
        "the same page (K+ 3.3-5.0: start insulin; 0.1 units/kg/hr after K+ >=3.3; hold if K+ <3.3)",
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
