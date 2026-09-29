#!/usr/bin/env python3
"""
fix_truncated_crisis_resources.py — two burnout pages that start to give a crisis line and stop.

WHY THIS EXISTS
Found 2026-09-28 while checking an unrelated truncation. It is the most consequential defect
this corpus has produced, and it had been invisible to every gate the repo has.

    icu-nurse-burnout-signs-prevention-2026:
        "If you are experiencing a mental health crisis, please contact the 988 Suicide
    nurse-burnout-recovery-plan-2026:
        "If you are in crisis, please contact the

Both stop there. The raw HTML runs straight into <div id="related-articles"> with the <p>
never closed. The second is the worse of the two: it names NO resource at all, and "988"
appears ZERO times anywhere on that page. A nurse in crisis, reading the sentence that page
wrote for exactly that reader, is handed nothing.

WHY IT WAS INVISIBLE, which is the reusable part
Three separate green checks all looked straight at these pages and reported them clean:
  - check_site_integrity.html_severity() does not count <p> as a block tag, so div_delta,
    block_delta and unterminated are all fine.
  - tests/corpus_baseline.json has no entry, and the corpus gate treats "no baseline entry"
    as "must be clean" — measured by the same metric that cannot see this.
  - the disclaimer test checks that disclaimer LANGUAGE is present. It is present. It is also
    cut in half. Presence and completeness are different questions, and only one was asked.
This is the "a green gate only means what it measures" lesson from CLAUDE.md, a third time,
and the first time it has hidden something that could matter to a person rather than to SEO.

It is a CLASS, not two pages. Twenty-seven pages carry this closing attribution paragraph and
ALL TWENTY-SEVEN are unclosed and cut mid-sentence -- zero well-formed. Most are legal, tax or
practice disclaimers ("does not constitute tax advice. Con", "Always consult a licensed tax
professional who special"). Those are NOT repaired here and must not be deleted: a truncated
disclaimer is still protective language, and standing priority 3 requires clinical pages to
carry one. Completing them would mean writing new copy, which is the owner's. Only the two
crisis-resource instances are fixed, because only those two can be completed from wording this
site already publishes, and only those two have a reader in an emergency.

WHY THIS IS PROPAGATION AND NOT INVENTION
The completion is the publisher's own phrase, and for the first page it is on the SAME PAGE,
eleven lines above the truncation:

    icu-nurse-burnout-signs-prevention-2026 (same file):
        "The Nurse Support Line (1-800-662-0108) and the 988 Suicide and Crisis Lifeline
         are available 24/7."
    icu-nurse-burnout-recovery.html:
        "please reach out to a mental health provider or, in crisis, contact the
         988 Suicide and Crisis Lifeline."
    nurse-burnout-2026.html:
        "If you are experiencing thoughts of self-harm, please contact the 988 Suicide and
         Crisis Lifeline (call or text 988) or the Crisis Text Line..."

The second page's truncated stem is "please contact the", which is character-for-character the
stem nurse-burnout-2026 completes with "988 Suicide and Crisis Lifeline (call or text 988)".
No number, name or claim is introduced that this site does not already publish. Nothing here
was taken from memory.

The </p> each paragraph was missing is closed at the same time, since a repair that leaves the
tag open re-creates the condition that hid the damage.

SCOPE AND SAFETY
Two exact substrings in two files, each verified to occur EXACTLY ONCE before this script was
written; the script re-checks at run time and refuses any file where the count is not 1.

IDEMPOTENT: neither replacement contains its own pattern (each ends in the completed phrase
plus </p>, so the bare truncated stem no longer matches).

USAGE
    python3 fix_truncated_crisis_resources.py --dry-run
    python3 fix_truncated_crisis_resources.py
"""

from __future__ import annotations

import sys

from safe_write import safe_write_html

# (file, old, new, why, the page whose wording supplies the completion)
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "icu-nurse-burnout-signs-prevention-2026.html",
        "please contact the 988 Suicide\n",
        "please contact the 988 Suicide and Crisis Lifeline (call or text 988).</p>\n",
        "crisis sentence cut mid-name; the <p> never closed",
        "the SAME page ('the 988 Suicide and Crisis Lifeline are available 24/7'), "
        "plus nurse-burnout-2026.html for the '(call or text 988)' form",
    ),
    (
        "nurse-burnout-recovery-plan-2026.html",
        "please contact the\n",
        "please contact the 988 Suicide and Crisis Lifeline (call or text 988).</p>\n",
        "crisis sentence cut before naming ANY resource; '988' appears nowhere on this page",
        "nurse-burnout-2026.html ('please contact the 988 Suicide and Crisis Lifeline "
        "(call or text 988)') - an identical sentence stem",
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
        print(f"      -       {old.strip()}")
        print(f"      +       {new.strip()}")
        if not dry:
            safe_write_html(path, updated, allow_preexisting=True)
        changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}{changed} edit(s) applied, {skipped} skipped.")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
