#!/usr/bin/env python3
"""
add_legal_footer_links.py — every ad-serving page must link to the privacy policy.

WHY THIS EXISTS
622 of 1,461 pages carry the AdSense loader and do NOT link to a privacy policy anywhere on
the page. Google's publisher policies require a privacy disclosure covering cookie and
third-party ad usage, and GDPR/CCPA both assume the policy is reachable from the page that
collects the data. A policy that exists but is unreachable from 43% of the site is not a
disclosure.

Two shapes, both handled:
    488 pages  have a <footer> but no legal links   -> append a legal row inside it
    134 pages  have no <footer> at all              -> insert a minimal footer

The legal row links Privacy Policy, Affiliate Disclosure and Terms. All three target pages
were verified to exist on disk, so this cannot introduce a broken link — and
check_index()'s broken-link scan would catch it on index.html if it did.

Affiliate Disclosure is included deliberately: the site carries Amazon and referral links,
and the FTC expects the disclosure to be reachable, not buried on one page.

IDEMPOTENT: a page already linking the privacy policy is skipped.

USAGE
    python3 add_legal_footer_links.py --dry-run
    python3 add_legal_footer_links.py
"""
from __future__ import annotations

import os
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

LEGAL_TARGETS = ["privacy-policy.html", "affiliate-disclosure.html", "terms-of-service.html"]

LEGAL_ROW = (
    '  <p style="font-size:0.85em;color:#9ca3af;">'
    '<a href="privacy-policy.html" style="color:#9ca3af;">Privacy Policy</a> &middot; '
    '<a href="affiliate-disclosure.html" style="color:#9ca3af;">Affiliate Disclosure</a> &middot; '
    '<a href="terms-of-service.html" style="color:#9ca3af;">Terms</a></p>\n'
)

MINIMAL_FOOTER = "<footer>\n" + LEGAL_ROW + "</footer>\n"

# Pages that are themselves the legal documents, or that legitimately have no footer.
SKIP = {"404.html", "google-verify.html"}


def needs_link(text: str) -> bool:
    return "privacy-policy.html" not in text and "privacy.html" not in text


def add_links(text: str) -> str | None:
    """Return the page with a reachable privacy link, or None if it already has one."""
    if not needs_link(text):
        return None

    at = text.rfind("</footer>")
    if at != -1:
        return text[:at] + LEGAL_ROW + text[at:]

    at = text.rfind("</body>")
    if at == -1:
        return None  # no safe insertion point; leave it rather than guess
    return text[:at] + MINIMAL_FOOTER + text[at:]


def main() -> int:
    dry = "--dry-run" in sys.argv

    missing = [t for t in LEGAL_TARGETS if not os.path.exists(os.path.join(HERE, t))]
    if missing:
        print(f"ABORT — link targets do not exist: {missing}")
        return 1

    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html") and f not in SKIP)
    into_footer = new_footer = skipped = refused = no_anchor = 0

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        if not needs_link(text):
            skipped += 1
            continue

        had_footer = "</footer>" in text
        new_text = add_links(text)
        if new_text is None:
            no_anchor += 1
            print(f"  NO ANCHOR {name}: neither </footer> nor </body>")
            continue

        if had_footer:
            into_footer += 1
        else:
            new_footer += 1

        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}legal row added to existing footer: {into_footer} | "
          f"minimal footer created: {new_footer}")
    print(f"  already linked: {skipped} | no anchor: {no_anchor} | refused: {refused}")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
