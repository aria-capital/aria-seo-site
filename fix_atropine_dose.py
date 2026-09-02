#!/usr/bin/env python3
"""
fix_atropine_dose.py — correct one outdated clinical dose across the corpus.

WHY THIS EXISTS
The 2026-08-19 clinical hold pulled product `vrseeu` partly because its ACLS card printed
bradycardia atropine as 0.5 mg. The 2020 AHA adult bradycardia algorithm raised the first
dose to 1 mg (repeat every 3-5 min, max 3 mg); 0.5 mg is the pre-2020 figure. The product
was held. Nobody searched the ARTICLES that share its generator, and the same value was
still live in five of them eight weeks later — three advertised to Google.

WHY A CORRECTION AND NOT A DELETION
Standing priority 5 prefers removing a false statement over *adding a qualifying one* — it
forbids papering over a falsehood with a hedge, not replacing a wrong number with the right
one. Deleting the figure would also leave `code-blue-nursing-guide-2026`'s drug table with an
empty dose cell, which is worse for the reader than either. So this corrects the value.

WHY THIS IS NOT A CLINICAL JUDGEMENT BY A SCRIPT
It is not deciding anything: 1 mg is the published algorithm value and is the same figure the
owner's own clinical hold already identified as correct. The script only propagates a
correction that was already made once, to the artifacts nobody swept.

WHAT IT WILL NOT TOUCH
0.5 mg is correct for other atropine indications (antisialagogue, organophosphate titration,
some paediatric use). A bare `0.5 mg` near the word atropine is therefore NOT sufficient —
this requires a bradycardia/ACLS context word within the same window, and it rewrites only
the dose that sits directly after the drug name. Every skipped file is reported, not silently
passed over.

IDEMPOTENT: a second run changes nothing, because the pattern only matches 0.5.

USAGE
    python3 fix_atropine_dose.py --dry-run
    python3 fix_atropine_dose.py
"""

from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

from safe_write import safe_write_html

# The drug name, then up to 60 chars of markup/whitespace, then the dose. Bounded so it
# cannot leap from one table row to a dose belonging to a different drug.
DOSE = re.compile(r"(?is)(atropine\b.{0,60}?)(\b0\.5\s*mg\b)")
CONTEXT = re.compile(r"(?i)brady|heart block|symptomatic|acls|algorithm|pacing|code blue|asystole")
WINDOW = 300


def correct(html: str) -> tuple[str, int]:
    """Return (new_html, n_changed). Only rewrites doses in a bradycardia/ACLS context."""
    out = []
    last = 0
    n = 0
    for m in DOSE.finditer(html):
        near = html[max(0, m.start() - WINDOW):m.end() + WINDOW]
        if not CONTEXT.search(near):
            continue
        out.append(html[last:m.start()])
        out.append(m.group(1) + "1 mg")
        last = m.end()
        n += 1
    out.append(html[last:])
    return "".join(out), n


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = skipped = 0
    for path in sorted(glob.glob("*.html")):
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        if not re.search(r"(?i)atropine", html):
            continue
        new, n = correct(html)
        if n == 0:
            if re.search(r"(?is)atropine.{0,60}?\b0\.5\s*mg\b", html):
                print(f"  SKIPPED (no bradycardia/ACLS context — 0.5 mg may be correct): {path}")
                skipped += 1
            continue
        print(f"  {'would fix' if dry else 'fixed'} {n}x  {path}")
        if not dry:
            safe_write_html(path, new, allow_preexisting=True)
        changed += 1
    print(f"\n{'[dry-run] ' if dry else ''}{changed} file(s) corrected, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
