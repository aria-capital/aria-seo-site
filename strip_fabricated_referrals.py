#!/usr/bin/env python3
"""
strip_fabricated_referrals.py — remove referral links to programs nobody is enrolled in.

WHY THIS EXISTS
Eight outbound links across six pages point at fabricated referral URLs:

    https://sofi.com/referral/?via=aria           (5)
    https://hosthealthcare.com/refer/?via=aria    (3)

The `?via=aria` format matches no real affiliate program. The vault's own records
confirm why: ARIA_AFFILIATE_LINKS.txt — the file designated to hold real referral URLs —
is blank ("Fill in each link after signing up"), and project_travel_nurse_referral.md
records that the Host Healthcare signup never happened. Zero affiliate programs are
approved.

So these links do two bad things at once:
  * they earn nothing, because there is no account behind them
  * they carry rel="nofollow sponsored" and sit in copy that reads as a paid endorsement,
    which misrepresents a commercial relationship that does not exist. That is the FTC
    problem, and it is the one that matters — an unpaid link is a missed opportunity, a
    falsely-disclosed one is a misrepresentation.

WHAT IT DOES
Unwraps the anchor, keeping the visible text. The sentence still reads naturally and the
reader loses nothing — they simply are not sent through a referral that does not exist.
Removing the link cannot create new exposure; adding a real one is the owner's job once a
program actually approves them.

IDEMPOTENT.

USAGE
    python3 strip_fabricated_referrals.py --dry-run
    python3 strip_fabricated_referrals.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# Hosts we have positive evidence are NOT enrolled. Keep this list tight: a link to a
# program that IS approved must not be stripped.
FABRICATED = re.compile(
    r'<a\b[^>]*href="https?://(?:www\.)?(?:sofi|hosthealthcare|credible|atitesting)\.com'
    r'[^"]*[?&]via=aria[^"]*"[^>]*>(.*?)</a>',
    re.I | re.S,
)


# The same fabricated URL also appears as bare prose, e.g.
#   "Connect via our link: hosthealthcare.com/refer/?via=aria."
# which claims a referral relationship just as plainly as an anchor does.
BARE_TEXT = re.compile(
    r"\s*Connect via our link:\s*(?:https?://)?(?:www\.)?"
    r"(?:sofi|hosthealthcare|credible|atitesting)\.com[^\s<]*[?&]via=aria[^\s<]*\.?",
    re.I,
)


def strip(text: str) -> tuple[str, int]:
    """Unwrap fabricated referral anchors and drop bare-text referral claims."""
    text, n1 = FABRICATED.subn(lambda m: m.group(1), text)
    text, n2 = BARE_TEXT.subn("", text)
    return text, n1 + n2


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    changed = removed = refused = 0
    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text, n = strip(text)
        if not n:
            continue

        changed += 1
        removed += n
        print(f"  {name}: {n} link(s) unwrapped")
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            changed -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}pages changed: {changed} | "
          f"links removed: {removed} | refused: {refused}")
    if not dry and removed:
        print("  Copy is preserved; only the non-existent referral targets are gone.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
