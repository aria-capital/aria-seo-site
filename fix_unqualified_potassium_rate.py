#!/usr/bin/env python3
"""
fix_unqualified_potassium_rate.py — remove an IV potassium RATE that no route qualifies.

WHAT IS WRONG
`diabetes-dka-hhs-nursing-guide-2026` (advertised) tells the reader:

    K+ <3.3 mEq/L: HOLD insulin; replace potassium aggressively (20-40 mEq/hr IV)
    until K+ >=3.5, THEN start insulin

40 mEq/hr is double the highest rate this site permits anywhere else, and the sentence names no
route and no monitoring — just "IV". Every other potassium page here caps the rate at 10-20 mEq/hr
and ties anything above 10 to cardiac monitoring and central access. Measured over the whole
corpus, this is the ONLY potassium rate figure above 20 mEq/hr in 1,462 files; the other eleven
all sit at 10 or 20.

Where the number came from is visible one line below it:

    K+ 3.3-5.0: start insulin; add K+ to IV fluids (20-40 mEq per liter)

"20-40 mEq per LITER" is a CONCENTRATION and is unremarkable. The bullet above reprinted those
digits as a RATE. Rate-for-concentration is the same conflation behind the other potassium defects
repaired in this corpus, and it is the one that kills: 40 mEq/L in a bag is routine, 40 mEq/hr
into a vein is not.

WHY THIS DELETES RATHER THAN CORRECTS
Standing priority 5, and consistency with the house. `fix_inverted_potassium.py` faced the same
choice on two sibling pages and removed the false figures without substituting new ones, on the
grounds that removing an untrue claim cannot create new exposure while choosing a replacement is
clinical judgement belonging to the owner, who is the RN. The same reasoning applies here, so the
same remedy applies here.

An earlier draft of this repair did substitute a figure — "begin at 10 mEq/hr", the 2024
ADA/EASD consensus value — and it survived three source-fetching skeptics. It is not used, because
it would have made this page the only potassium page in the corpus carrying a rate the house had
just decided to stop printing. Corpus consistency beat a well-sourced number. If the owner later
wants the guideline figure restored across all the potassium pages at once, that is one decision
taken deliberately, not a fourth variant introduced by a repair script.

"aggressively" goes with the number. With the figure removed it is an unquantified urging toward
exactly the behaviour that was wrong, and the instruction survives intact without it: hold insulin,
replace potassium until K+ >=3.5, then start insulin. That is the sequence the bullet exists for.

DELIBERATELY OUT OF SCOPE
The 3.3 threshold. It is the superseded 2009 figure (the 2024 consensus says 3.5), but
"hold below 3.3, replete until >=3.5" is legitimate hysteresis rather than an error, and the value
appears at eight sites across four files plus a card in index.html. Changing this one site alone
would make the page order HOLD insulin and START insulin for a K+ of 3.4, two bullets apart. That
is its own atomic commit.

WHY THE EXISTING GUARD DID NOT CATCH THIS
`tests/test_fix_inverted_potassium.py` looks for a PERIPHERAL figure at or above the CENTRAL figure
beside it, which requires a route word within 90 characters of the number. This sentence has no
route word at all, so that guard leaves the figure unlabelled and reports the page clean — verified
by running it. The two guards are complementary, not redundant: one catches route pairs that are
backwards, the other catches rates with no route at all. See the test file.

IDEMPOTENT: the anchor cannot match the replacement.

USAGE
    python3 fix_unqualified_potassium_rate.py --dry-run
    python3 fix_unqualified_potassium_rate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from safe_write import safe_write_html

PATH = "diabetes-dka-hhs-nursing-guide-2026.html"

# Matched EXACTLY against the live bytes. Note the non-ASCII: the line carries U+2013 EN DASH and a
# literal U+2265, not "-" and "&ge;". An anchor written in the ASCII spelling matches nothing and
# reports success — which is how a prepared version of this edit was found to be a silent no-op
# before it ran.
FIND = "replace potassium aggressively (20–40 mEq/hr IV) until K+ ≥3.5"
REPLACE = "replace potassium until K+ ≥3.5"


def correct(html: str) -> tuple[str, int]:
    """Return (new_html, n_changed)."""
    n = html.count(FIND)
    return (html.replace(FIND, REPLACE), n) if n else (html, 0)


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    p = Path(PATH)
    if not p.exists():
        print(f"  MISSING FILE: {PATH}")
        return 1
    html = p.read_text(encoding="utf-8")
    new, n = correct(html)
    if not n:
        if REPLACE in html:
            print(f"  skip (already corrected): {PATH}")
            return 0
        print(f"  ANCHOR NOT FOUND — page reworded since this was written: {PATH}")
        print("  Refusing to guess. Re-derive the anchor from the live bytes before re-running.")
        return 1
    print(f"  {'would remove' if dry else 'removed'} the unqualified rate {n}x  {PATH}")
    if not dry:
        safe_write_html(PATH, new, allow_preexisting=True)
    print(f"\n{'[dry-run] ' if dry else ''}done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
