#!/usr/bin/env python3
"""
fix_verified_dose_errors.py — ten clinical statements that contradict the rest of this site.

WHY THIS EXISTS
A coverage audit read 118 advertised, dose-bearing pages end to end (1,091 individual dose
expressions) rather than matching drug/dose pairs with a regex — the gap named in CLAUDE.md as
"covers only the drug/dose pairs the extractor matched." It produced 25 candidates. Each was then
attacked by independent skeptics instructed to REFUTE it and to default to refuted when uncertain,
with three separate lenses on the high-severity ones:

    clinical   — is the page actually wrong as a matter of practice?
    corpus     — do the cited sibling quotes REALLY exist, verbatim, and say what was claimed?
    falsepos   — read in full context, is there a reading under which the page is RIGHT?

Sixteen candidates went to verification; nine survived; ten edits are applied here (one page
carries two). The pass is only as trustworthy as the things it killed, so those are recorded in
"WHAT THE VERIFICATION REJECTED" below — two of them had been reported as high-severity and were
false positives.

WHY THIS IS NOT A SCRIPT INVENTING CLINICAL CONTENT
Seven of the ten edits replace a value with wording this site ALREADY PUBLISHES on another page,
and the source page is named for each. The other three DELETE a claim the site itself disproves;
nothing is written in their place. No edit introduces a number that was not already on the site,
which is the rule that makes an automated clinical repair reviewable at all.

    standing priority 1 — never publish a claim the site cannot support
    standing priority 5 — prefer removing a false statement over adding a qualifying one

THE TEN EDITS

1. push-dose-pressors: a 10x dilution error, provable from the page's own numbers.
   "take 1 mL from a cardiac epinephrine syringe (100 mcg/mL) and inject it into a 100 mL bag — or
   ... into a 9 mL flush — to reach 10 mcg/mL". 1 mL of 100 mcg/mL is 100 mcg; into 100 mL that is
   1 mcg/mL, not 10. The flush route in the same sentence DOES give 10 mcg/mL, so the sentence
   offers two "equivalent" routes that differ tenfold. The bag recipe needs 1 mg, i.e. the whole
   syringe, not 1 mL of it. Harm path: a nurse mixes per the bag route, labels it 10 mcg/mL, gives
   the page's own 2 mL bolus for post-intubation hypotension expecting 20 mcg, and delivers 2 mcg.
   FIX: keep the page's own correct flush clause, drop the bag clause.

2. hypertensive-crisis: hydralazine for eclampsia at up to 2x the per-dose, with NO ceiling.
   The row's only stated indication is "Eclampsia/preeclampsia" and it prints "10–20 mg IV q20 min"
   with no cumulative maximum, so three repeats is 60 mg in 40 minutes. This site's own dedicated
   page publishes 5–10 mg q20 min, max 20–30 mg. Hydralazine's signature harm is exactly stacked
   doses peaking together — which this site's own drug page describes in plain words.
   FIX: the dedicated page's regimen, verbatim.

3+4. iv-push-medication-safety: the phenytoin diluent, inverted, twice, in a warning box headed
   "absolute contraindications that have caused deaths". Phenytoin precipitates in DEXTROSE;
   normal saline is the REQUIRED diluent. The second instance is doubly inverted — it names saline
   as incompatible and prescribes D5W as the remedy, i.e. the one fluid that precipitates it.
   A nurse following it during status epilepticus produces microcrystalline precipitate and an
   undelivered anticonvulsant. Six correct statements exist elsewhere on this site.
   FIX: both clauses, using the sibling page's wording.

5. arterial-line: a transducer-leveling factor ~2.7x too large.
   "reads falsely LOW BP (by ~2 mmHg per cm above)". 1 cmH2O = 0.74 mmHg, so 1 cm of leveling
   error is ~0.75 mmHg. The figure "2 mmHg" belongs to 2.5 cm — which is how the other three pages
   on this site state it, all agreeing with each other and with the physics. This is the only page
   in the corpus giving a per-centimetre figure. Harm path runs both ways: a nurse finding a
   transducer 10 cm high computes a 20 mmHg artifact where the real one is ~7, and may "correct" a
   MAP of 55 up to 75 — or dismiss a genuinely low pressure as an artifact.
   FIX: restate per 2.5 cm, the site's own framing.

6. fluid-electrolyte-balance: magnesium toxicity bands printed in the wrong unit AND shifted one
   row toward severity. "4–7 mg/dL: loss of deep tendon reflexes" — but 4–7 mg/dL is 3.3–5.8
   mEq/L, which is INSIDE the therapeutic range for seizure prophylaxis. A nurse checking a
   patellar reflex against this table treats a therapeutic level as early toxicity.
   FIX: the four-band mEq/L sequence this site publishes on its preeclampsia page.

7. peripartum-cardiomyopathy: the only weight-based furosemide dose in the corpus.
   "IV furosemide at 1–2.5 mg/kg" is 70–175 mg for a 70 kg, typically diuretic-naive postpartum
   woman — and the same page warns two sentences later "do not over-diurese: a dilated, hypokinetic
   ventricle is preload-dependent."
   FIX: this site's own acute-decompensation dose.

8. liver-failure: "terlipressin (not available in US)" — FDA-approved since September 2022, and
   this site's own dedicated page calls it "the first drug approved in the U.S." for hepatorenal
   syndrome. DELETE the stale parenthetical; no replacement needed.

9. icp-monitoring: "(Some centers target 50–60 for aSAH...)" inside the CPP formula box. No page
   on this site supports a 50–60 mmHg CPP band for aSAH, and this page contradicts itself four
   lines later by calling CPP 55 "borderline inadequate". DELETE; the box's remaining
   "CPP 60–70 mmHg" line matches the rest of the site.

10. ai-medication-safety: "(example: norepinephrine maximum of 10 mcg/kg/min being overridden in
    40% of septic shock cases)". 10 mcg/kg/min is ~20x this site's own stated ceiling of
    0.5 mcg/kg/min, and the 40% figure is sourced nowhere. An invented statistic on a page about
    medication safety is standing priority 1 squarely. DELETE.

WHAT THE VERIFICATION REJECTED — recorded because a pass is only as good as its false positives
  * cardiac-dysrhythmia "adenosine 6 mg rapid IV push if unstable" — reported as an inverted
    stability qualifier. REFUTED 2/3. The AHA Adult Tachycardia With a Pulse algorithm's UNSTABLE
    box reads "Synchronized cardioversion / Consider sedation / If regular narrow complex, consider
    adenosine", and the row's own Key Features cell supplies "Regular, very fast; narrow QRS". The
    finding applied the textbook simplification, not the governing protocol.
  * diabetes-dka-hhs "20–40 mEq/hr IV" potassium for K+ <3.3 — reported as double the site's own
    ceiling. REFUTED 2/3. Both endpoints are published for this exact indication (ADA 2009:
    20–30 mEq/h; Merck Manual: 40 mEq/hour until K+ >= 3.3 with insulin held). DKA with K+ <3.3 is
    a recognised exception to the general peripheral ceiling, not a typo.
  Four more were refuted 2/2 and one 1/2; none is edited here.

SCOPE AND SAFETY
Ten exact substrings across nine files. Every old string was checked to occur EXACTLY ONCE in its
file before this script was written; the script re-checks at run time and refuses any file where
the count is not 1, rather than guessing. No regex, no fuzzy matching — a substring that has been
reworded since simply reports and is skipped.

IDEMPOTENT: no replacement contains its own pattern, so a second run matches nothing.

USAGE
    python3 fix_verified_dose_errors.py --dry-run
    python3 fix_verified_dose_errors.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why-in-one-line, source page for the wording)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "push-dose-pressors-icu-nurses-2026.html",
        "inject it into a 100 mL bag &mdash; or, more practically at the bedside, "
        "into a 9 mL flush &mdash; to reach 10 mcg/mL",
        "inject it into a 9 mL flush to reach 10 mcg/mL",
        "1 mL of 100 mcg/mL into 100 mL is 1 mcg/mL, not 10 — a tenfold underdose of a rescue pressor",
        "the page's own flush clause; epinephrine-guide-icu-nurses-2026.html",
    ),
    (
        "hypertensive-crisis-nursing-guide-2026.html",
        "10–20 mg IV q20 min (unpredictable, slow onset)",
        "5–10 mg IV q20 min; max 20–30 mg (unpredictable, slow onset)",
        "obstetric hydralazine at up to 2x the per-dose with no cumulative ceiling",
        "preeclampsia-hellp-nursing-guide-2026.html",
    ),
    (
        "iv-push-medication-safety-icu-nurses-2026.html",
        "phenytoin in normal saline (precipitates)",
        "phenytoin in dextrose-containing fluids (precipitates)",
        "diluent inverted inside a 'has caused deaths' warning box; NS is the required diluent",
        "phenytoin-fosphenytoin-guide-icu-nurses-2026.html",
    ),
    (
        "iv-push-medication-safety-icu-nurses-2026.html",
        "phenytoin + anything in saline (precipitates — use dedicated line with D5W)",
        "phenytoin + dextrose-containing fluids (precipitates — normal saline only, "
        "ideally through a dedicated line)",
        "doubly inverted: names saline as incompatible and prescribes the fluid that precipitates it",
        "phenytoin-fosphenytoin-guide-icu-nurses-2026.html",
    ),
    (
        "arterial-line-nursing-guide-2026.html",
        "(by ~2 mmHg per cm above)",
        "(by ~2 mmHg per 2.5 cm — about one inch — above)",
        "leveling factor ~2.7x too large; 1 cmH2O = 0.74 mmHg, so 2 mmHg belongs to 2.5 cm",
        "pressure-transducer-leveling-zeroing-icu-nurses-2026.html",
    ),
    (
        "fluid-electrolyte-balance-nursing-guide-2026.html",
        "4–7 mg/dL: loss of deep tendon reflexes (earliest sign — check patellar reflex "
        "before each dose); 7–10 mg/dL: respiratory depression (respiratory arrest risk); "
        "&gt;10 mg/dL: cardiac arrest.",
        "4–7 mEq/L: therapeutic range — seizure prophylaxis; 7–10 mEq/L: loss of deep "
        "tendon reflexes (earliest sign — check patellar reflex before each dose); "
        "10–13 mEq/L: respiratory depression (respiratory arrest risk); "
        "&gt;15 mEq/L: cardiac arrest.",
        "magnesium bands in the wrong unit and shifted one row: 4-7 mg/dL is therapeutic, not toxic",
        "preeclampsia-hellp-nursing-guide-2026.html",
    ),
    (
        "peripartum-cardiomyopathy-icu-nurses-2026.html",
        "IV furosemide at 1&ndash;2.5 mg/kg",
        "furosemide 40&ndash;80 mg IV push (or 2.5x home dose)",
        "only weight-based furosemide in the corpus; 70-175 mg in a preload-dependent patient",
        "congestive-heart-failure-nursing-guide-2026.html",
    ),
    (
        "liver-failure-nursing-guide-2026.html",
        " (not available in US)",
        "",
        "terlipressin has been FDA-approved since 2022; this site's own page says so",
        "deletion — no replacement invented",
    ),
    (
        "icp-monitoring-icu-nurses-2026.html",
        "(Some centers target 50–60 for aSAH; verify with your neurology/neurosurgery team)",
        "",
        "no page supports a 50-60 CPP band for aSAH; this page calls CPP 55 inadequate four lines later",
        "deletion — no replacement invented",
    ),
    (
        "ai-medication-safety-nurses-2026.html",
        " (example: norepinephrine maximum of 10 mcg/kg/min being overridden in 40% of septic shock cases)",
        "",
        "10 mcg/kg/min is ~20x this site's own ceiling and the 40% figure is sourced nowhere",
        "deletion — no replacement invented",
    ),
]


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = 0
    skipped = 0

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
            # Not "close enough" — refuse rather than guess. A reworded target means a human
            # should look, and a silent no-op is exactly how a repair pretends to have run.
            print(f"SKIP  {path}: pattern occurs {count} times, expected exactly 1")
            print(f"      ({why})")
            skipped += 1
            continue

        updated = text.replace(old, new)
        if old in updated:
            print(f"SKIP  {path}: replacement still contains the pattern — not idempotent, refusing")
            skipped += 1
            continue

        print(f"{'[dry-run] ' if dry else ''}FIX   {path}")
        print(f"      why:    {why}")
        print(f"      source: {source}")
        print(f"      -       {old[:96]}")
        print(f"      +       {(new or '(deleted)')[:96]}")
        if not dry:
            safe_write_html(path, updated, allow_preexisting=True)
        changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}{changed} edit(s) applied, {skipped} skipped.")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
