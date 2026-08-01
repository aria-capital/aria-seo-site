#!/usr/bin/env python3
"""
fix_cookie_banner.py — repair the truncated GDPR/CCPA cookie-consent block.

WHY THIS EXISTS
The cookie banner was injected across the article corpus by a writer that was cut
off mid-write, so the block landed truncated in 599 of the 755 files that carry
it. The cut lands in three places, all damaging:

  * mid-`style=` attribute (337 files) — the attribute is never closed, so a real
    browser parser swallows every following tag into the attribute value until it
    finds the next quote. The newsletter block and everything after it stop
    rendering. This is the worst of the three and the least visible.
  * mid-`<span>` body (~200 files) — leaves an unclosed <div>, which is the +1
    div imbalance that shows up on 849 articles.
  * mid-`<script>` (53 files) — leaves a dangling script with no </script>.

The block is a fixed, machine-generated snippet, so the repair is not a merge:
excise the damaged region and re-emit the one canonical copy.

IDEMPOTENT: a file already carrying the canonical block is left untouched, so
this is safe to run repeatedly.

Writes go through safe_write_html(allow_preexisting=True) — the repair may not
make any file worse, but it is allowed to leave a file that is still damaged in
unrelated ways (many articles are independently truncated).

USAGE
    python3 fix_cookie_banner.py --dry-run   # report only, write nothing
    python3 fix_cookie_banner.py             # apply
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError, html_severity
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

BANNER_OPEN = '<div id="cookie-banner"'
BANNER_LEAD = "<!-- COOKIE CONSENT BANNER"
BANNER_END = "<!-- END COOKIE BANNER -->"

# A well-formed opening tag keeps its whole style attribute on one line and
# closes it. The truncated copies run off the end of the line instead.
WELLFORMED_OPEN = re.compile(r'<div id="cookie-banner" style="[^"\n]*">')

# The banner block contains none of these, so the first one appearing after the
# banner starts marks where the block ends and the next sibling begins. This is
# what lets one rule handle all three cut points.
SIBLING_MARKERS = (
    "<!-- ICU Notebook",
    '<div id="related-articles"',
    "<!-- AFFILIATE-CTA",
    "<footer",
    "</body>",
)

CANONICAL = """<!-- COOKIE CONSENT BANNER — GDPR/CCPA -->
<div id="cookie-banner" style="display:none;position:fixed;bottom:0;left:0;right:0;background:#1a1a2e;color:#e5e7eb;padding:14px 20px;font-family:sans-serif;font-size:0.83em;z-index:9999;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
  <span>We use cookies for analytics and advertising (Google AdSense). By continuing, you accept our
    <a href="privacy-policy.html" style="color:#22c55e;">Privacy Policy</a>.
    EU/California visitors: you may opt out via your browser settings or
    <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener" style="color:#22c55e;">Google Ad Settings</a>.
  </span>
  <button onclick="document.getElementById('cookie-banner').style.display='none';localStorage.setItem('cookieConsent','1');"
    style="background:#22c55e;color:#000;border:none;padding:8px 18px;border-radius:4px;cursor:pointer;font-weight:600;white-space:nowrap;">
    Got it
  </button>
</div>
<script>
(function(){
  try { if(!localStorage.getItem('cookieConsent')) { document.getElementById('cookie-banner').style.display='flex'; } } catch(e){}
})();
</script>
<!-- END COOKIE BANNER -->"""


def find_region(text: str) -> tuple[int, int] | None:
    """
    Locate the cookie-banner block as (start, end) character offsets, or None if
    the file carries no banner. `end` is exclusive.
    """
    div = text.find(BANNER_OPEN)
    if div == -1:
        return None

    # Absorb the lead-in comment when it sits immediately before the div, so the
    # replacement doesn't leave a second orphaned copy of it behind.
    start = div
    lead = text.rfind(BANNER_LEAD, max(0, div - 200), div)
    if lead != -1:
        close = text.find("-->", lead)
        if close != -1 and close < div and not text[close + 3:div].strip():
            start = lead

    end_marker = text.find(BANNER_END, div)
    if end_marker != -1 and WELLFORMED_OPEN.match(text, div):
        return start, end_marker + len(BANNER_END)

    # Damaged: end the region at the next sibling block.
    candidates = [p for p in (text.find(m, div + len(BANNER_OPEN)) for m in SIBLING_MARKERS) if p != -1]
    return (start, min(candidates)) if candidates else (start, len(text))


def repair(text: str) -> str | None:
    """Return the repaired document, or None if nothing needs doing."""
    region = find_region(text)
    if region is None:
        return None
    start, end = region
    if text[start:end] == CANONICAL:
        return None  # already canonical — idempotent no-op
    # The excised region often swallowed the blank line that separated the banner
    # from the next block, so re-establish a newline rather than butting the two
    # together. It sits outside the region, keeping the equality check above exact.
    tail = text[end:]
    separator = "" if tail.startswith("\n") else "\n"
    return text[:start] + CANONICAL + separator + tail


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    repaired = skipped = failed = 0
    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text = repair(text)
        if new_text is None:
            skipped += 1
            continue

        before, after = html_severity(text), html_severity(new_text)
        if dry:
            print(f"  would repair {name}: div_delta {before['div_delta']}->{after['div_delta']}, "
                  f"unterminated_attr {before['unterminated_attr']}->{after['unterminated_attr']}")
            repaired += 1
            continue

        try:
            safe_write_html(path, new_text, allow_preexisting=True)
            repaired += 1
        except IntegrityError as exc:
            failed += 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}repaired: {repaired} | already clean/no banner: {skipped} | refused: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
