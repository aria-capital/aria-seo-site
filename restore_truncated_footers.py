#!/usr/bin/env python3
"""
restore_truncated_footers.py — re-attach the tail of three <footer> blocks that were
cut off mid-write.

WHY THIS EXISTS
Three pages carry a <footer> with no </footer>. The cut landed inside the footer's link
list, so the document keeps going but the footer never closes and everything after it —
the newsletter block, the related-articles card, the cookie banner — is swallowed into it
by the browser's error recovery.

Two of the three are invisible to the current gates. `html_severity()` counts </head>,
</body>, </html> and <div>, but not <footer>, so `check_article_corpus.py` scores
dmca-policy.html and nurse-real-estate-investing.html as clean. They are not. (This script
is paired with adding footer balance to html_severity() so the gap cannot reopen.)

WHY RESTORE RATHER THAN EXCISE
The truncation repair that came before this one discarded damaged trailing blocks
wholesale, and in doing so deleted 171 recoverable newsletter forms. The lesson recorded in
CLAUDE.md is to check whether git history or the healthy corpus can complete a fragment
before throwing it away. All three fragments here are byte-exact PREFIXES of a complete
block that still exists — so nothing is invented and nothing is lost:

  crna-salary-by-state-2026.html      prefix of a block that occurs 115x in the live corpus
  dmca-policy.html                    prefix of the block at ed22a310, modulo the
                                      2026-07 "ARIA Capital Holdings LLC" -> "ICU Notebook"
                                      footer rename in da672544
  nurse-real-estate-investing.html    prefix of the block at ed22a310, same rename

The exact-prefix requirement is the safety property: a canonical is only applied when the
bytes already on disk are its opening bytes, so the repair can only ever ADD the missing
tail. If no canonical matches, the file is skipped and reported rather than guessed at.

IDEMPOTENT — a balanced <footer> is not a truncated one, so a second run finds nothing.

USAGE
    python3 restore_truncated_footers.py --dry-run
    python3 restore_truncated_footers.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# Complete <footer> blocks, verbatim. Provenance is in the module docstring; each is only
# ever applied to a file whose bytes are already an exact prefix of it.
CANONICAL_FOOTERS = [
    # Live corpus, 115 occurrences (the &copy;/&middot; entity-encoded variant).
    '<footer>\n'
    '  <div class="container" style="text-align:center;padding:20px;">\n'
    '    <p>&copy; 2026 ICU Notebook &middot; '
    '<a href="privacy-policy.html" style="color:#9ca3af;text-decoration:none;">Privacy Policy</a> &middot; '
    '<a href="affiliate-disclosure.html" style="color:#9ca3af;text-decoration:none;">Affiliate Disclosure</a> &middot; '
    '<a href="contact.html" style="color:#9ca3af;text-decoration:none;">Contact</a></p>\n'
    '  </div>\n'
    '  <div style="text-align:center;padding:4px 0;font-size:0.8em;">'
    '<a href="terms-of-service.html" style="color:#9ca3af;text-decoration:none;">Terms</a> &middot; '
    '<a href="dmca-policy.html" style="color:#9ca3af;text-decoration:none;">DMCA</a></div>\n'
    '</footer>',

    # ed22a310:dmca-policy.html, with the footer brand rename from da672544 applied.
    '<footer>\n'
    '<p>© 2026 ICU Notebook &middot;\n'
    '<a href="index.html">Home</a> &middot;\n'
    '<a href="privacy-policy.html">Privacy Policy</a> &middot;\n'
    '<a href="terms-of-service.html">Terms of Service</a> &middot;\n'
    '<a href="affiliate-disclosure.html">Affiliate Disclosure</a>\n'
    '</p>\n'
    '</footer>',

    # ed22a310:nurse-real-estate-investing.html, same rename.
    '<footer>\n'
    '  <p>© 2026 ICU Notebook | <a href="index.html">Home</a> | Educational content only. '
    'Not financial advice. Real estate investing involves significant risk and is not '
    'appropriate for all investors.</p>\n'
    '</footer>',
]

FOOTER_TOKEN = re.compile(r"<footer\b|</footer>")


def truncated_footer_span(html: str) -> tuple[int, int] | None:
    """
    (start, end) of the first <footer> fragment that never closes, or None.

    Matching is stack-based rather than "is there a </footer> anywhere after this one".
    nurse-real-estate-investing.html is why: its unclosed footer is followed by a SECOND,
    complete footer, so a naive lookahead finds that one's </footer> and calls the first
    one closed.

    The fragment runs to the first blank line, which is where the next injected block
    begins — the writers separate blocks with one. That boundary is what makes the
    fragment comparable to a canonical: everything after it belongs to a different block
    and must be preserved untouched.
    """
    stack: list[int] = []
    for m in FOOTER_TOKEN.finditer(html):
        if m.group(0) == "</footer>":
            if stack:
                stack.pop()
        else:
            stack.append(m.start())
    if not stack:
        return None
    start = stack[0]
    gap = html.find("\n\n", start)
    return (start, len(html) if gap == -1 else gap)


def restore(html: str) -> str | None:
    """Repaired document, or None if there is nothing to do / nothing safe to do."""
    span = truncated_footer_span(html)
    if span is None:
        return None
    start, end = span
    fragment = html[start:end]
    matches = [c for c in CANONICAL_FOOTERS if c.startswith(fragment)]
    if len(matches) != 1:
        return None  # ambiguous or unknown — the caller reports it rather than guessing
    return html[:start] + matches[0] + html[end:]


def main() -> int:
    dry = "--dry-run" in sys.argv
    repaired: list[str] = []
    skipped: list[str] = []

    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        if before.count("<footer") == before.count("</footer>"):
            continue

        after = restore(before)
        if after is None:
            skipped.append(f"{name}: no single canonical footer is a prefix of the fragment")
            continue
        if after.count("<footer") != after.count("</footer>"):
            skipped.append(f"{name}: still unbalanced after restore")
            continue
        worse = severity_regressions(html_severity(before), html_severity(after))
        if worse:
            skipped.append(f"{name}: refused, would regress — " + "; ".join(worse))
            continue

        repaired.append(f"{name}: +{len(after) - len(before)} bytes restored")
        if not dry:
            safe_write_html(path, after, allow_preexisting=True)

    verb = "would restore" if dry else "restored"
    print(f"{verb}: {len(repaired)} file(s)")
    for line in repaired:
        print("  +", line)
    if skipped:
        print(f"skipped: {len(skipped)} file(s)")
        for line in skipped:
            print("  -", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
