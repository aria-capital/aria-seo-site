#!/usr/bin/env python3
"""
apply_noindex_to_uncurated.py — make the sitemap curation actually mean something.

WHY THIS EXISTS

Commit b8476741 (2026-08-05) measured the real answer with a Google `site:` query:
the homepage is indexed and **zero of the 1,461 articles are**. So Google has crawled
this site and declined it. That is a different problem from never being found, and it
has the opposite fix — you cannot repair a quality verdict by advertising more URLs.

The curated 940-URL sitemap was built to stop the site presenting as a content farm.
Measured today, it does not do that. 522 articles are live but not advertised, and each
is linked from 10-43 pages that ARE advertised. Crawlers follow links. So Google reaches
all 1,461 regardless of the sitemap and assesses the site on its weakest pages.

`<meta name="robots" content="noindex, follow">` is the only mechanism that actually
withholds a page from assessment. `follow` is deliberate: the links still pass through,
so nothing is orphaned and internal link equity still flows to the curated set.

WHY THIS IS SAFE TO DO NOW, AND WHY IT WOULD NOT BE LATER
Zero articles are currently indexed. There is no ranking, no traffic and no revenue to
lose — the downside of noindex is normally "you lose the traffic that page earned", and
that quantity is measurably zero. If any of these pages ever start ranking, this becomes
a real trade-off and should be revisited. Reversing it is one flag: `--remove`.

WHAT IT DOES NOT DO
It does not delete, hide, unlink or alter a single word of any article. Every page stays
live, reachable and readable by humans. This changes only what crawlers are invited to
judge.

SELECTION
The curated set is read from sitemap.xml itself, so this can never drift from the sitemap:
whatever is advertised is exactly what stays indexable. Core/meta pages are never touched.

USAGE
    python3 apply_noindex_to_uncurated.py --dry-run
    python3 apply_noindex_to_uncurated.py
    python3 apply_noindex_to_uncurated.py --remove      # full reversal
"""
from __future__ import annotations

import os
import re
import sys

from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))
SITEMAP = os.path.join(HERE, "sitemap.xml")

TAG = '<meta name="robots" content="noindex, follow">'

# Linked from every page and part of the site's structure, not its content corpus.
# Excluding them from the sitemap is a navigation decision, not a quality judgement,
# so they must never be de-indexed by this rule.
NEVER_TOUCH = {
    "index.html", "about.html", "contact.html", "privacy-policy.html", "privacy_policy.html",
    "affiliate-disclosure.html", "terms-of-service.html", "dmca-policy.html",
    "all-articles.html", "404.html", "google-verify.html", "start-here.html",
}

_HEAD = re.compile(r"(?i)<head[^>]*>")
_EXISTING_ROBOTS = re.compile(r'(?i)<meta\s+name=["\']robots["\'][^>]*>\s*\n?')


def curated_slugs() -> set[str]:
    """The advertised set, read from the sitemap so the two can never disagree."""
    with open(SITEMAP, encoding="utf-8") as fh:
        locs = re.findall(r"<loc>([^<]+)</loc>", fh.read())
    return {loc.rstrip("/").split("/")[-1] for loc in locs if loc.endswith(".html")}


def targets() -> list[str]:
    curated = curated_slugs()
    return sorted(
        name for name in os.listdir(HERE)
        if name.endswith(".html") and name not in NEVER_TOUCH and name not in curated
    )


def add_noindex(html: str) -> str:
    """
    Insert the tag immediately after <head>. Idempotent: an existing robots meta of any
    value is replaced rather than stacked, so re-running is a no-op and a page that said
    "index, follow" is corrected rather than left contradicting itself.
    """
    if TAG in html and len(_EXISTING_ROBOTS.findall(html)) == 1:
        return html
    html = _EXISTING_ROBOTS.sub("", html)
    return _HEAD.sub(lambda m: m.group(0) + "\n" + TAG, html, count=1)


def remove_noindex(html: str) -> str:
    """Full reversal: drop the tag we added, leaving the document as it was."""
    return html.replace(TAG + "\n", "").replace("\n" + TAG, "").replace(TAG, "")


def main() -> int:
    dry = "--dry-run" in sys.argv
    removing = "--remove" in sys.argv
    transform = remove_noindex if removing else add_noindex

    names = targets()
    changed = skipped = refused = 0
    problems: list[str] = []

    for name in names:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            before = fh.read()

        if not _HEAD.search(before):
            problems.append(f"{name}: no <head> found, skipped")
            refused += 1
            continue

        after = transform(before)
        if after == before:
            skipped += 1
            continue
        if not dry:
            try:
                # allow_preexisting: bulk edit to existing articles, per repo rule 2.
                # The write is still refused the instant it makes any metric worse.
                safe_write_html(path, after, allow_preexisting=True)
            except Exception as exc:  # noqa: BLE001 - report, never abort the batch
                problems.append(f"{name}: {exc}")
                refused += 1
                continue
        changed += 1

    verb = "would remove from" if (dry and removing) else \
           "would add to" if dry else \
           "removed from" if removing else "added to"
    print(f"  uncurated articles      : {len(names)}")
    print(f"  {verb:<22}: {changed}")
    print(f"  already correct         : {skipped}")
    print(f"  refused/skipped         : {refused}")
    for p in problems[:10]:
        print(f"    ! {p}")
    if dry:
        print("\n[dry-run] nothing written.")
    else:
        print("\n  Every article remains live and reachable. This changes only what")
        print("  crawlers are invited to assess.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
