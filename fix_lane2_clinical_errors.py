#!/usr/bin/env python3
"""
fix_lane2_clinical_errors.py — eleven more figures this site contradicts on its own pages.

WHY THIS EXISTS
The cross-page contradiction lane (48 high-alert drugs compared across every advertised page
naming them) and three drug-agnostic error-shape lanes ran for the first time on 2026-09-28 —
a session rate limit had killed them twice. Twenty-eight candidates; three were already fixed
(atropine, fosphenytoin, magnesium thresholds); these eleven follow.

EVERY EDIT IS EITHER
  PROPAGATE — the correction is wording this site already publishes, source page named; or
  REMOVE    — the statement is false and no correct replacement exists on the site, so the
              false clause is deleted and nothing is written in its place
              (standing priority 5: removing an untrue claim cannot create new exposure).

No edit introduces a number that was not already on this site.

THE EDITS

1. crrt-nurse-guide — citrate toxicity described with the WRONG ACID-BASE DIRECTION.
   "Total calcium rising while ionized calcium falls (Ca:iCa ratio >2.5), metabolic alkalosis,
   increasing anion gap." Citrate ACCUMULATION — the hepatic-failure scenario the same
   sentence names — produces a rising-anion-gap metabolic ACIDOSIS. The sentence already
   contradicts itself: "increasing anion gap" is the acidosis signature.
   The site says so twice: hemodialysis-crrt-nursing-guide has a near-identical sentence
   ending "...ratio &gt;2.5; high anion gap metabolic acidosis", and
   acute-kidney-injury-crrt-icu-nurses says "a widening gap — often with a worsening
   metabolic acidosis". PROPAGATE.

2. cardiac-dysrhythmia — "epinephrine + amiodarone every cycle" in the VF/pVT row.
   Amiodarone in arrest is TWO doses total (300 mg, then 150 mg), never per cycle, and
   epinephrine is every 3-5 minutes. "Every cycle" turns a two-dose antiarrhythmic into a
   repeating one. Five pages state the real cadence, including this page's own drug table
   four rows down. PROPAGATE from code-blue-nursing-guide and amiodarone-guide.

3. cardiac-dysrhythmia — magnesium row lists ECLAMPSIA but prints only the torsades dose.
   "Torsades de Pointes; eclampsia; hypomagnesemia | 1-2g IV slowly". 1-2 g is the
   torsades/repletion dose; eclampsia is a 4-6 g load then 1-2 g/hr, which this site states on
   three pages — magnesium-sulfate-guide even tabulates the two separately. PROPAGATE.

4. seizure-nursing-guide — lorazepam "4-hr half-life".
   No published half-life matches 4 h (elimination is ~12-14 h), and no page on this site
   states one, so there is nothing to propagate. REMOVE the figure; the rest of the cell
   (first-line for SE, respiratory depression, have a BVM) is correct and stays.

5. alcohol-withdrawal-ciwa — a benzodiazepine-resistance threshold that belongs to DIAZEPAM.
   ">40-60 mg lorazepam in 1 hour" is 10-30x this page's own hourly PRN dose. A first-hour
   requirement in the 40 mg range is the diazepam-equivalent definition; lorazepam is several
   times more potent per milligram. This site publishes no lorazepam resistance threshold, so
   there is no number to propagate. REMOVE the figure and keep the escalation instruction,
   which is the clinically useful part. Raised independently by THREE lanes.

6. critical-care-medications — succinylcholine onset "60-90 sec".
   paralytics-guide-icu-nurses: "onset in ~30-60 seconds and duration of only ~5-10 minutes".
   PROPAGATE both the onset and the duration cell in the same row.

7. critical-care-medications — "If BG <70: hold insulin + give D50W 25 mL IV; recheck q30 min".
   Four pages say recheck at 15 minutes, including this site's dedicated D50 guide and the DKA
   page's identical phrasing "recheck q15 min". Thirty minutes is long enough for a patient on
   a held insulin drip to fall again unobserved. PROPAGATE.

8. fluid-electrolytes — "Magnesium (Normal: 1.5-2.5 mg/dL)".
   1.5-2.5 are the digits this site uses for magnesium in mEq/L; where it reports mg/dL it says
   1.7-2.2 (nursing-medical-abbreviations-guide). The numbers are right and the LABEL is wrong.
   Fixing the label rather than the numbers also keeps the table's own "<1.5" / ">2.5" column
   headers correct, and makes the whole section consistent with the mEq/L toxicity bands
   corrected on this page earlier today. PROPAGATE (the unit, not the figures).

9. lab-values — "INR &gt;1.5 before invasive procedures".
   A verbless fragment whose direction is carried entirely by the comparator, and the
   comparator is backwards: medication-safety-high-alert-drugs says "hold for invasive
   procedures (INR must be &lt;1.5)". As printed it reads as a target to reach rather than a
   ceiling to stay under. PROPAGATE.

10. vancomycin-guide — "no faster than 1 gram per hour (or 10 mg/min)".
    The two figures are presented as equivalents and are not: 1 g/hr is 16.7 mg/min, 10 mg/min
    is 600 mg/hr. The page's own schedule (1.5-2 g over 90-120 min) follows the per-hour
    figure. No page states a per-minute vancomycin ceiling, so there is nothing to propagate.
    REMOVE the parenthetical; the correct per-hour rate and the reason for it both stay.

11. renal-failure — "Regular insulin 10u IV".
    The dose is correct and is NOT changed. The defect is the abbreviation: "u" for units is
    the ISMP error-prone abbreviation that reads as 0 or 4, and this is the only page in the
    corpus that uses it — this site's own medication-safety pages teach against it. Spelling
    it out changes no number.

12. nursing-handoff-shift-report — "Last PTT at 1400 was 78 — sub-therapeutic".
    Every page here puts the heparin therapeutic aPTT at 60-100 seconds, so 78 is mid-range.
    It is a teaching script rather than a dosing instruction, but it teaches the number on the
    wrong side of this site's own threshold. PROPAGATE.

WHAT IS DELIBERATELY NOT FIXED — each needs a number or a judgement this site does not supply
  * medication-error-prevention "3% saline: central line only" — the site's own osmotherapy
    pages allow peripheral. Loosening a conservative access rule is not a change to make on a
    lane finding; it is the owner's call.
  * pca-pump naloxone dilution — the conventional dilution is not stated anywhere on the site.
  * diabetes-dka-hhs K+ 3.3 vs 3.5 inside one protocol box — BOTH are published thresholds and
    the corpus is split 4:4. Making it consistent means choosing one.
  * liver-failure albumin "1 g/kg/day" with no cap — the day-1 vs maintenance split needs a
    figure the site does not publish.
  * amiodarone-vs-lidocaine — lidocaine repeat-bolus ceiling is an OMISSION, not an error.

SCOPE AND SAFETY
Thirteen exact substrings across ten files. Each was checked to occur EXACTLY ONCE before this
script was written; the script re-checks at run time and refuses any file where the count is
not 1. No regex, no fuzzy matching.

IDEMPOTENT: no replacement contains its own pattern.

USAGE
    python3 fix_lane2_clinical_errors.py --dry-run
    python3 fix_lane2_clinical_errors.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, source page for the wording — or "deletion")
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "crrt-nurse-guide-2026.html",
        "metabolic alkalosis, increasing anion gap",
        "high anion gap metabolic acidosis",
        "citrate ACCUMULATION causes acidosis; the sentence already said 'increasing anion gap'",
        "hemodialysis-crrt-nursing-guide-2026.html / acute-kidney-injury-crrt-icu-nurses-2026.html",
    ),
    (
        "cardiac-dysrhythmia-nursing-guide-2026.html",
        "epinephrine + amiodarone every cycle",
        "epinephrine 1 mg every 3&ndash;5 min; amiodarone 300 mg IV/IO push, then 150 mg for a "
        "second dose (two doses total)",
        "amiodarone in arrest is two doses, never per cycle; epinephrine is q3-5 min",
        "code-blue-nursing-guide-2026.html / amiodarone-guide-icu-nurses-2026.html",
    ),
    (
        "cardiac-dysrhythmia-nursing-guide-2026.html",
        "1&ndash;2g IV slowly",
        "1&ndash;2 g IV slowly for torsades or repletion; eclampsia is a 4&ndash;6 g IV load "
        "over 15&ndash;20 min then 1&ndash;2 g/hr",
        "row names eclampsia but prints only the torsades dose",
        "magnesium-sulfate-guide-icu-nurses-2026.html / preeclampsia-hellp-nursing-guide-2026.html",
    ),
    (
        "seizure-nursing-guide-2026.html",
        "First-line for acute SE; 4-hr half-life (shorter than diazepam); respiratory depression",
        "First-line for acute SE; respiratory depression",
        "no published half-life is 4 h and the site states none — removed rather than invented",
        "deletion — no replacement invented",
    ),
    (
        "alcohol-withdrawal-ciwa-nursing-guide-2026.html",
        "If patient requires &gt;40–60 mg lorazepam in 1 hour without improvement → Add phenobarbital",
        "If the patient is not improving despite escalating hourly lorazepam dosing → Add phenobarbital",
        "40-60 mg/hr is a DIAZEPAM-equivalent threshold; the site publishes no lorazepam figure",
        "deletion — no replacement invented",
    ),
    (
        "critical-care-medications-nursing-guide-2026.html",
        "fastest onset (60–90 sec)",
        "fastest onset (30–60 sec)",
        "four sibling pages say ~30-60 s; this page is the lone outlier in the slower direction",
        "paralytics-guide-icu-nurses-2026.html",
    ),
    (
        "critical-care-medications-nursing-guide-2026.html",
        "<td>8–12 min</td>",
        "<td>5–10 min</td>",
        "succinylcholine duration; the same sibling page says ~5-10 min",
        "paralytics-guide-icu-nurses-2026.html",
    ),
    (
        "critical-care-medications-nursing-guide-2026.html",
        "recheck q30 min",
        "recheck q15 min",
        "four pages incl. the dedicated D50 guide say 15 min after IV dextrose",
        "dextrose-d50-hypoglycemia-guide-icu-nurses-2026.html / diabetes-dka-hhs-nursing-guide-2026.html",
    ),
    (
        "fluid-electrolytes-nursing-guide-2026.html",
        "Magnesium (Normal: 1.5&ndash;2.5 mg/dL)",
        "Magnesium (Normal: 1.5&ndash;2.5 mEq/L)",
        "1.5-2.5 are this site's mEq/L digits; in mg/dL it publishes 1.7-2.2. The label was wrong",
        "nursing-medical-abbreviations-guide-2026.html (Mg normal 1.7-2.2 mg/dL)",
    ),
    (
        "lab-values-nursing-guide-2026.html",
        "INR &gt;1.5 before invasive procedures",
        "INR must be &lt;1.5 before invasive procedures",
        "comparator backwards: 1.5 is a ceiling to stay under, not a target to reach",
        "medication-safety-high-alert-drugs-nursing-guide-2026.html",
    ),
    (
        "vancomycin-guide-icu-nurses-2026.html",
        "<strong>1 gram per hour</strong> (or 10 mg/min)",
        "<strong>1 gram per hour</strong>",
        "1 g/hr is 16.7 mg/min, not 10; the page's own schedule follows the per-hour figure",
        "deletion — no replacement invented",
    ),
    (
        "renal-failure-nursing-guide-2026.html",
        "Regular insulin 10u IV",
        "Regular insulin 10 units IV",
        "'u' is the ISMP error-prone abbreviation that reads as 0 or 4; the dose is unchanged",
        "this site's own medication-safety pages teach against 'u'",
    ),
    (
        "nursing-handoff-shift-report-guide-2026.html",
        "was 78 — sub-therapeutic",
        "was 78 — therapeutic",
        "every page here puts the heparin therapeutic aPTT at 60-100 s, so 78 is mid-range",
        "the site's own heparin pages",
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
        print(f"      source: {source}")
        print(f"      -       {old[:100]}")
        print(f"      +       {new[:100]}")
        if not dry:
            safe_write_html(path, updated, allow_preexisting=True)
        changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}{changed} edit(s) applied, {skipped} skipped.")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
