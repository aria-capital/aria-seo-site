#!/usr/bin/env python3
"""
fix_canonicals.py — every page declares exactly one canonical URL, pointing at the
host that actually serves it.

WHY THIS EXISTS
A canonical tag tells Google "the authoritative version of this page lives at X". Get it
wrong and the page is not merely unranked — it is de-indexed in favour of a URL that may
not exist. Three states are live in this corpus:

  1,249 pages  correct    -> https://aria-capital.github.io/aria-seo-site/<file>
    192 pages  MISSING    -> Google picks a URL itself, and may split ranking signals
                             across duplicates instead of consolidating them
     ~14 pages  WRONG     -> point at hosts that do not serve this content:
                               example.com               (3 pages, placeholder never replaced)
                               ariacapitalholdings.com   (custom domain, not the live host)
                               carlostrujillo.github.io  (an older project)
                               nursetofinancialfreedom.com

The example.com ones are the worst: a canonical to a domain you do not control hands the
page away. Those pages cannot rank at all while it stands.

The live host is taken from _config.yml (url + baseurl), the same source generate_sitemap.py
uses, so the sitemap and the canonicals cannot drift apart. Commit c795a01 ("point canonicals
at the live host") established this intent; this finishes it.

IDEMPOTENT. Adds the tag immediately before </head> when absent.

USAGE
    python3 fix_canonicals.py --dry-run
    python3 fix_canonicals.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from generate_sitemap import read_base_url
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

CANONICAL_RE = re.compile(r'[ \t]*<link[^>]+rel="canonical"[^>]*>\n?', re.I)
HREF_RE = re.compile(r'rel="canonical"[^>]*href="([^"]*)"', re.I)

# Pages that should not advertise a canonical of their own.
SKIP = {"404.html", "google-verify.html"}

# A canonical pointing at a DIFFERENT local page is legitimate when two pages are genuine
# near-duplicates and one is nominated as authoritative. Forcing self-canonical would then
# destroy a deliberate consolidation, so such pairs belong here and are left alone.
#
# The corpus currently contains exactly one cross-page canonical, and it was checked:
#   how-to-become-crna-2026.html -> how-to-become-a-crna-2026.html
# The two share 0.07 text similarity — unrelated articles, not duplicates. It was pointing
# Google away from a page toward something entirely different, so it is corrected, not kept.
CROSS_CANONICAL_ALLOWLIST: dict[str, str] = {}


def expected_url(base: str, name: str) -> str:
    """The canonical URL for a page. index.html canonicalises to the clean root."""
    if name in CROSS_CANONICAL_ALLOWLIST:
        return base + CROSS_CANONICAL_ALLOWLIST[name]
    return base if name == "index.html" else base + name


def fix(text: str, want: str) -> tuple[str, str]:
    """Return (new_text, action) where action is 'ok' | 'added' | 'corrected' | 'deduped'."""
    found = CANONICAL_RE.findall(text)
    current = HREF_RE.search(text)

    tag = f'<link rel="canonical" href="{want}">'

    if not found:
        if "</head>" not in text:
            return text, "no-head"
        return text.replace("</head>", f"{tag}\n</head>", 1), "added"

    action = "ok"
    if len(found) > 1:
        action = "deduped"
    elif not current or current.group(1) != want:
        action = "corrected"

    if action == "ok":
        return text, "ok"

    # Collapse any number of canonical tags into exactly one correct tag, in place of the first.
    first = CANONICAL_RE.search(text)
    text = CANONICAL_RE.sub("", text)
    head = text.find("</head>")
    insert_at = min(first.start(), head) if head != -1 else first.start()
    return text[:insert_at] + tag + "\n" + text[insert_at:], action


def main() -> int:
    dry = "--dry-run" in sys.argv
    base = read_base_url()
    # Walk, do not listdir. `os.listdir(HERE)` sees the repo root only, so the 15
    # pages under pet_care/ were never processed and shipped with NO canonical at
    # all — and tests/test_fix_canonicals.py asserted "every live page has exactly
    # one canonical" using the same flat scan, so it passed while the pages were
    # broken. The same non-recursive assumption is why those pages are absent from
    # the sitemap. `expected_url()` already handles a nested name correctly,
    # because it just appends the repo-relative path to the base URL.
    files = []
    for dirpath, dirnames, filenames in os.walk(HERE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "tests", "store-covers")]
        for f in filenames:
            if not f.endswith(".html"):
                continue
            name = os.path.relpath(os.path.join(dirpath, f), HERE)
            if name in SKIP or os.path.basename(name) in SKIP:
                continue
            files.append(name)
    files = sorted(files)

    counts: dict[str, int] = {}
    refused = 0
    corrected_samples: list[str] = []

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        want = expected_url(base, name)
        before = HREF_RE.search(text)
        new_text, action = fix(text, want)
        counts[action] = counts.get(action, 0) + 1

        if action in ("corrected", "deduped") and len(corrected_samples) < 8:
            corrected_samples.append(f"    {name}: {before.group(1) if before else '?'} -> {want}")

        if action in ("ok", "no-head") or dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}base URL: {base}")
    for k in ("ok", "added", "corrected", "deduped", "no-head"):
        if counts.get(k):
            print(f"  {k:10s} {counts[k]}")
    if refused:
        print(f"  refused    {refused}")
    if corrected_samples:
        print("\n  sample corrections:")
        print("\n".join(corrected_samples))
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
