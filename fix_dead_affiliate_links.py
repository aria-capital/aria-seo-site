#!/usr/bin/env python3
"""Unlink Amazon affiliate links whose product does not exist.

Measured 2026-08-05: of 17 distinct ASINs across 36 pages, four are unusable —
two are fabricated placeholders (`B0C1234567`, `B0D1234567`, the same defect family as
the `?via=aria` referral links this repo already purged) and two return HTTP 404.

A dead affiliate link is strictly worse than no link: it earns nothing, and it sends a
reader who trusted the recommendation to a Not Found page.

**This removes the anchor and keeps the words.** Per repo rule 5, a repair may lose a link
but may never invent one — so no replacement ASIN is guessed. If a real product should be
linked there, that is a human decision, not a repair.

    python3 fix_dead_affiliate_links.py --dry-run
    python3 fix_dead_affiliate_links.py --apply
"""
import glob
import re
import sys

from safe_write import safe_write_html

# Verified 2026-08-05 by fetching each: placeholders serve Amazon's soft-404, the other
# two return a hard 404. Re-verify before adding to this list — an ASIN can come back.
DEAD_ASINS = {
    "B0C1234567": "fabricated placeholder",
    "B0D1234567": "fabricated placeholder",
    "1635839785": "HTTP 404",
    "1975163893": "HTTP 404",
}

# <a ...amazon.com/dp/ASIN...>text</a>  ->  text
LINK = re.compile(
    r'<a\b[^>]*?href="[^"]*amazon\.com/(?:dp|gp/product)/([A-Z0-9]{10})[^"]*"[^>]*>(.*?)</a>',
    re.I | re.S,
)


def strip_dead(html):
    """Return (new_html, {asin: count}). Keeps the anchor text, drops the anchor."""
    removed = {}

    def repl(m):
        asin, text = m.group(1), m.group(2)
        if asin in DEAD_ASINS:
            removed[asin] = removed.get(asin, 0) + 1
            return text
        return m.group(0)

    return LINK.sub(repl, html), removed


def main():
    apply_changes = "--apply" in sys.argv
    if not apply_changes and "--dry-run" not in sys.argv:
        print("pass --dry-run or --apply")
        return 2

    total, files, per_asin = 0, 0, {}
    for path in sorted(glob.glob("*.html")):
        html = open(path, encoding="utf-8").read()
        if "amazon.com" not in html:
            continue
        new, removed = strip_dead(html)
        if not removed:
            continue
        files += 1
        for a, n in removed.items():
            per_asin[a] = per_asin.get(a, 0) + n
            total += n
        if apply_changes:
            # Repo rule 1: never raw open(...,'w') on an article. Bulk edit of existing
            # files, so allow_preexisting=True — refuse only on regression.
            safe_write_html(path, new, allow_preexisting=True)

    print(("APPLIED" if apply_changes else "DRY RUN")
          + f" — {total} dead link(s) unlinked across {files} file(s)\n")
    for a in sorted(per_asin):
        print(f"  {per_asin[a]:3d}  {a}  ({DEAD_ASINS[a]})")
    if not total:
        print("  nothing to do — no dead affiliate links present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
