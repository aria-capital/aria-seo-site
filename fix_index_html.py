#!/usr/bin/env python3
"""
fix_index_html.py — repair the homepage's mid-file card-grid damage.

WHY THIS EXISTS
index.html is the only page check_site_integrity.py fails on, which is why CI runs that
check non-blocking. The damage is NOT end-of-file truncation — the file ends correctly with
`</div></body></html>`. It is six truncated `<div class="article-card">` blocks in the
middle of the grid, plus the three grid wrappers those breaks left open:

    div_delta 9 = 6 truncated cards + .grid + .container + .section
    </footer>   = 0   (the footer was lost with them)

So the article-corpus repair does NOT apply here. That rule cuts at the last trailing-block
marker; index.html has no gumroad, affiliate, cookie or newsletter marker in its trailing
region, so the rule would cut at the intact `<div id="related-articles">` — destroying good
content while leaving all six real defects in place.

REPAIR
Phase 1 heals the cards. A card is truncated iff it contains no `</div>` before the next
card opener. For each, the `<h3><a href="...">Title</a></h3>` is kept VERBATIM if it
survived intact, the partial `<p>` is discarded, and the div is closed. If the anchor did
not survive whole, the fragment is discarded outright — never guessed. Two guards make this
safe to rebuild rather than delete:
  * the target file must exist on disk, so no card links to a 404
  * the href must appear exactly once in the original document, so a rebuild cannot
    duplicate a card that already exists elsewhere in the grid

Phase 2 closes .grid/.container/.section at the end of the grid and restores the footer.
This makes the email-capture and related-articles blocks page-level siblings after the
section rather than children of an open .grid, which is where their own markup
(max-width:520px centred; full-width panel) shows they were meant to sit. Both are
preserved byte for byte.

Phase 3 gates the write with STRICT validation — no allow_preexisting. The homepage must
come out actually clean, not merely no-worse.

IDEMPOTENT.

USAGE
    python3 fix_index_html.py --dry-run
    python3 fix_index_html.py
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

from check_site_integrity import check_index, html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")

OPENER = '<div class="article-card"'
GRID_TERMINUS = "<!-- ICU Notebook -- email capture"
ANCHOR_RE = re.compile(r'<h3><a href="([a-z0-9\-]+\.html)">(.*?)</a></h3>')

FOOTER = """<footer>
  <div class="container" style="text-align:center;padding:20px;">
    <p>&copy; 2026 ICU Notebook &middot; <a href="privacy-policy.html" style="color:#9ca3af;text-decoration:none;">Privacy Policy</a> &middot; <a href="affiliate-disclosure.html" style="color:#9ca3af;text-decoration:none;">Affiliate Disclosure</a> &middot; <a href="contact.html" style="color:#9ca3af;text-decoration:none;">Contact</a></p>
  </div>
  <div style="text-align:center;padding:4px 0;font-size:0.8em;"><a href="terms-of-service.html" style="color:#9ca3af;text-decoration:none;">Terms</a> &middot; <a href="dmca-policy.html" style="color:#9ca3af;text-decoration:none;">DMCA</a></div>
</footer>
"""

GRID_CLOSE = "    </div>\n  </div>\n</div>\n\n"


def repair(html: str, site_dir: str = HERE) -> tuple[str, dict]:
    """Return (repaired_html, stats). Raises AssertionError if the file is not the shape we expect."""
    stats = {"rebuilt": 0, "discarded": 0, "healthy": 0, "grid_closed": 0, "footer_added": 0}

    if html.count(GRID_TERMINUS) != 1:
        raise AssertionError(
            f"expected exactly 1 {GRID_TERMINUS!r}, found {html.count(GRID_TERMINUS)}"
        )

    # Counted on the ORIGINAL text: a href seen once is safe to rebuild without duplicating.
    link_counts = Counter(re.findall(r'href="([a-z0-9\-]+\.html)"', html))

    term = html.index(GRID_TERMINUS)
    starts = [m.start() for m in re.finditer(re.escape(OPENER), html)]
    in_grid = [s for s in starts if s < term]

    edits: list[tuple[int, int, str]] = []
    for i, s in enumerate(in_grid):
        end = in_grid[i + 1] if i + 1 < len(in_grid) else term
        block = html[s:end]

        if "</div>" in block:
            stats["healthy"] += 1
            continue

        m = ANCHOR_RE.search(block)
        href = m.group(1) if m else None
        recoverable = (
            m is not None
            and os.path.exists(os.path.join(site_dir, href))
            and link_counts[href] == 1
        )

        if recoverable:
            edits.append((s, end,
                          f'<div class="article-card"><h3><a href="{href}">{m.group(2)}</a></h3></div>\n'))
            stats["rebuilt"] += 1
        else:
            # Also swallow the orphaned indent so no stray whitespace run is left behind.
            start = s
            nl = html.rfind("\n", 0, s)
            if nl != -1 and not html[nl + 1:s].strip():
                start = nl + 1
            edits.append((start, end, ""))
            stats["discarded"] += 1

    # Reverse order so earlier offsets stay valid as we splice.
    for start, end, replacement in reversed(edits):
        html = html[:start] + replacement + html[end:]

    # Phase 2 — close the three wrappers the truncated cards left open, restore the footer.
    term = html.index(GRID_TERMINUS)
    html = html[:term] + GRID_CLOSE + html[term:]
    stats["grid_closed"] = 3

    if "</footer>" not in html:
        b = html.index("</body>")
        html = html[:b] + FOOTER + html[b:]
        stats["footer_added"] = 1

    return html, stats


def main() -> int:
    dry = "--dry-run" in sys.argv
    with open(INDEX, encoding="utf-8", errors="replace") as fh:
        original = fh.read()

    before = html_severity(original)
    if not before["div_delta"] and original.count("</footer>") == 1:
        print("index.html already clean — nothing to do.")
        return 0

    repaired, stats = repair(original)
    after = html_severity(repaired)

    print(f"  cards: {stats['healthy']} healthy | {stats['rebuilt']} rebuilt from a surviving "
          f"<h3><a> | {stats['discarded']} discarded as unrecoverable")
    print(f"  grid wrappers closed: {stats['grid_closed']} | footer restored: {stats['footer_added']}")
    print(f"  severity: {before} -> {after}")

    regressions = severity_regressions(before, after)
    if regressions:
        print(f"  ABORT — repair would regress: {regressions}")
        return 1

    if dry:
        print("\n[dry-run] no files written.")
        return 0

    # Strict: the homepage must come out genuinely clean, not merely no-worse.
    safe_write_html(INDEX, repaired)

    problems = check_index()
    if problems:
        print("  WARNING — check_index still reports:")
        for p in problems:
            print("   -", p)
        return 1
    print("\n  check_index(): clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
