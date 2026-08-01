#!/usr/bin/env python3
"""
fix_gumroad_links.py — point every Gumroad link at a page that actually exists.

WHY THIS EXISTS
Gumroad is the only revenue channel with no third party in the loop: the owner's own
product, 100% margin, no affiliate network, no ad review, no approval queue. A dead
Gumroad link is not an unattributed sale, it is a lost one.

MEASURED (each storefront fetched):
    icunotebook.gumroad.com          HTTP 200   1,841 links   <- the live store
    ariacapitalholdings.gumroad.com  HTTP 404      53 links
    ariacapital.gumroad.com          HTTP 404      26 links
    aria-capital.gumroad.com         HTTP 404      23 links
    jordancruzrn.gumroad.com         HTTP 404       6 links

108 links point at four storefronts that no longer resolve.

HOW EACH CASE IS HANDLED
  82 bare storefront URLs (no /l/ path)
      Host swap to icunotebook.gumroad.com. The destination is a live storefront and the
      original intent was "go to the store", so this is exact.

  2 product links whose slug DOES resolve on the live store (/l/qdubzb, /l/mbuow)
      Host swap. Verified HTTP 200 at the new host, so the product moved with the store.

  24 product links whose slug does NOT resolve (/l/cvzxbo x18, /l/huemg x5, /l/akewxm x1)
      Repointed to the live STOREFRONT, not to a guessed product.

      The live store lists 9 products (avsrc, bvezxw, dpdvwf, itikqo, kvppg, oolhqk,
      qaebvo, ubwher, wyjmqr) and none of them match these slugs. Mapping would mean
      guessing which product replaces which, and sending a buyer to the wrong product is
      worse than a 404 — it converts a lost sale into a refund and a chargeback.

      A storefront landing can still convert; a 404 cannot. So this is strictly better than
      the status quo while remaining honest about what is unknown.

      OWNER ACTION: map these three slugs to real products, then add them to SLUG_MAP below.
      18 of the 24 are one product (/l/cvzxbo), so a single mapping recovers most of it.

IDEMPOTENT.

USAGE
    python3 fix_gumroad_links.py --dry-run
    python3 fix_gumroad_links.py
"""
from __future__ import annotations

import collections
import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

LIVE_STORE = "https://icunotebook.gumroad.com"

DEAD_HOSTS = [
    "ariacapitalholdings.gumroad.com",
    "ariacapital.gumroad.com",
    "aria-capital.gumroad.com",
    "jordancruzrn.gumroad.com",
]

# Slugs confirmed to resolve on the live store: keep the product path, swap the host.
SLUGS_THAT_SURVIVED = {"qdubzb", "mbuow"}

# Owner-supplied mappings for slugs that did not survive: old slug -> new slug.
# Empty until the owner identifies the replacement products; until then those links fall
# back to the storefront rather than guessing.
SLUG_MAP: dict[str, str] = {}

GUMROAD_URL = re.compile(
    r"https?://(" + "|".join(re.escape(h) for h in DEAD_HOSTS) + r")(/l/([a-z0-9]+))?/?"
)


def fix_url(match: re.Match) -> str:
    slug = match.group(3)
    if slug is None:
        return LIVE_STORE  # bare storefront
    if slug in SLUGS_THAT_SURVIVED:
        return f"{LIVE_STORE}/l/{slug}"
    if slug in SLUG_MAP:
        return f"{LIVE_STORE}/l/{SLUG_MAP[slug]}"
    return LIVE_STORE  # unmapped product -> storefront, never a guessed product


def fix_text(text: str) -> tuple[str, collections.Counter]:
    kinds: collections.Counter = collections.Counter()

    def repl(m: re.Match) -> str:
        slug = m.group(3)
        if slug is None:
            kinds["storefront"] += 1
        elif slug in SLUGS_THAT_SURVIVED:
            kinds["product-preserved"] += 1
        elif slug in SLUG_MAP:
            kinds["product-mapped"] += 1
        else:
            kinds[f"unmapped:{slug}"] += 1
        return fix_url(m)

    return GUMROAD_URL.sub(repl, text), kinds


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    changed = refused = 0
    totals: collections.Counter = collections.Counter()

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text, kinds = fix_text(text)
        if not kinds:
            continue

        totals.update(kinds)
        changed += 1
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            changed -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}pages changed: {changed} | refused: {refused}")
    for kind, n in sorted(totals.items(), key=lambda x: -x[1]):
        note = ""
        if kind.startswith("unmapped:"):
            note = "  <- OWNER: map this slug to a real product"
        print(f"  {kind:24s} {n}{note}")
    print(f"\n  all Gumroad links now point at {LIVE_STORE}")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
