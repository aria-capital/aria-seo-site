#!/usr/bin/env python3
"""
check_sitemap_curated.py — CI gate: the sitemap must stay a curation, not become a dump.

WHY THIS EXISTS
`safe_write.safe_write_sitemap()` now refuses any write that does not come from
`build_curated_sitemap.py`, which stops the three legacy writers at the moment of damage.
That is the primary guard. This is the backstop for everything it cannot see: a hand-edit,
a `git revert` of the curation commit, a merge that resurrects an old sitemap, or a script
written next year that bypasses safe_write entirely.

The repo has been bitten twice by a check that answered a narrower question than everyone
read it as, so it is worth being precise about what this does and does not assert.

WHAT IT ASSERTS
No article below the curator's own quality floor may be advertised. `build_curated_sitemap`
excludes anything under MIN_WORDS body words as thin; the core navigation pages are exempt
because they are linked from every page and belong in the sitemap as navigation, not as
ranked content.

WHY THAT INVARIANT AND NOT "the sitemap equals what the curator would produce"
Byte-equality is not usable: the curator stamps `<lastmod>` with `date.today()`, so an
exact comparison would pass on the day it was written and fail every day after. Set
equality is stable today but would fire on any legitimate content addition, since selection
ranks the corpus by word count and taking the top N reshuffles when N articles change — a
gate that goes red because someone published an article is a gate people learn to ignore,
which is the failure mode this repo exists to avoid.

The thin-article invariant has neither problem. It is stable across content growth, stable
across `--target` widening (a bigger batch still excludes thin pages), and it catches the
actual disaster precisely: a full-corpus dump advertises all 37 thin pages, so this fails
loudly the moment one lands.

WHAT IT DOES NOT ASSERT
That the sitemap is *exactly* the current curator output. A stale-but-still-curated sitemap
passes. That is deliberate — staleness is not the hazard, advertising the whole corpus is.

USAGE
    python3 check_sitemap_curated.py        # exit 1 if a thin article is advertised
"""
from __future__ import annotations

import os
import re
import sys

from build_curated_sitemap import CORE_PAGES, MIN_WORDS, body_words

HERE = os.path.dirname(os.path.abspath(__file__))
SITEMAP = os.path.join(HERE, "sitemap.xml")


def advertised_slugs(xml: str) -> set[str]:
    """The local filename behind every <loc>, ignoring the bare-root core URL."""
    out = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        slug = loc.rstrip("/").split("/")[-1]
        if slug.endswith(".html"):
            out.add(slug)
    return out


def thin_articles() -> dict[str, int]:
    """Non-core articles under the curator's quality floor, with their body word count."""
    core = set(CORE_PAGES)
    out: dict[str, int] = {}
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html") or name in core:
            continue
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
            words = body_words(fh.read())
        if words < MIN_WORDS:
            out[name] = words
    return out


def problems() -> list[str]:
    if not os.path.exists(SITEMAP):
        return ["sitemap.xml does not exist"]
    with open(SITEMAP, encoding="utf-8") as fh:
        advertised = advertised_slugs(fh.read())
    thin = thin_articles()
    return [
        f"{name} is advertised but has only {words} body words (floor is {MIN_WORDS})"
        for name, words in sorted(thin.items())
        if name in advertised
    ]


def main() -> int:
    found = problems()
    with open(SITEMAP, encoding="utf-8") as fh:
        advertised = advertised_slugs(fh.read())
    total = len([n for n in os.listdir(HERE) if n.endswith(".html")])

    print(f"sitemap advertises {len(advertised)} of {total} articles | "
          f"thin articles in the corpus: {len(thin_articles())}")

    if found:
        print(f"\nFAIL — {len(found)} thin article(s) are being advertised:")
        for line in found:
            print("  -", line)
        print(f"\nThe sitemap looks like a full-corpus dump rather than a curation. "
              f"Rebuild it with:\n    python3 build_curated_sitemap.py")
        return 1

    print("PASS — every advertised article clears the curator's quality floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
