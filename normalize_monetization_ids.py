#!/usr/bin/env python3
"""
normalize_monetization_ids.py — make every page use the ONE real AdSense publisher
and the ONE real Amazon Associates tag.

WHY THIS EXISTS
Two monetization identities drifted into the corpus, and in both cases the wrong one won.

AdSense
    ads.txt is the authorized-sellers file: it declares which publisher may sell ad
    inventory on a domain. Ad code running under a publisher the crawled ads.txt does not
    list reads as unauthorized inventory, and demand does not bid on it.

    THE CRAWLED ads.txt IS AT THE ROOT OF THE HOST, NOT AT THE PROJECT SUBPATH.
    Verified by fetching both:

      https://aria-capital.github.io/ads.txt                -> pub-5576001602612111  <-- authoritative
      https://aria-capital.github.io/aria-seo-site/ads.txt  -> pub-6510170611627184  <-- never fetched

    The root file lives in a DIFFERENT repository (the aria-capital.github.io org Pages
    repo) which is not part of this checkout. The ads.txt in this repo is an ordinary text
    file at a subpath; no crawler reads it, and it must not be used as evidence of which
    account is real.

    An earlier revision of this script got that backwards. It reasoned from the subpath
    copy, concluded 6510... was authoritative, and rewrote all 1,460 pages to it — moving
    them AWAY from the publisher the crawled ads.txt authorizes, and breaking a
    configuration that was already consistent.

    Provenance, re-read with the correct file:
      ca91ea4 2026-07-13  "Add AdSense ca-pub-6510170611627184 to all pages"
      08ca615 2026-07-17  subpath ads.txt added with the same ID
      b93bf9f 2026-07-21  1453-article bulk generation switched the pages to 5576...
    The ROOT ads.txt also says 5576..., and the deployed site serves 5576... Those two
    agree, which is what a working configuration looks like. The most likely history is an
    account change around 2026-07-21 that updated the pages and the root ads.txt, leaving
    only the unread subpath copy stale.

    STILL UNCONFIRMED: nobody has read the AdSense console. The owner should verify the
    publisher ID there. If it turns out to be 6510..., flip REAL_ADSENSE_PUB and
    WRONG_ADSENSE_PUBS and re-run — and update the ROOT ads.txt in the other repo, which
    is the file that actually decides this.

Amazon Associates
    ariacapital-20     54 links, first seen 2026-07-06, hardcoded in inject_affiliate_links.py
    aria-affiliate-20  18 links, first seen inside "Resolve 1111 merge conflicts"
    Only one tag can be the real account; the other earns $0 on every click. The earlier
    tag, which matches the org name and the injector's own source, is the real one.

IDEMPOTENT: re-running changes nothing once the corpus is normalized.

USAGE
    python3 normalize_monetization_ids.py --dry-run
    python3 normalize_monetization_ids.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html, safe_write_text

HERE = os.path.dirname(os.path.abspath(__file__))
ADS_TXT = os.path.join(HERE, "ads.txt")

# The authoritative identities. Change these ONLY with evidence, and update the
# provenance note above when you do.
REAL_ADSENSE_PUB = "5576001602612111"
REAL_AMAZON_TAG = "ariacapital-20"

WRONG_ADSENSE_PUBS = ["6510170611627184"]
WRONG_AMAZON_TAGS = ["aria-affiliate-20"]


def normalize(text: str) -> tuple[str, dict]:
    """Return (new_text, counts_of_each_replacement)."""
    counts: dict[str, int] = {}

    for wrong in WRONG_ADSENSE_PUBS:
        # Match the ID only in a publisher context so a bare number elsewhere in an
        # article's prose can never be rewritten.
        pattern = re.compile(r"(ca-pub-|pub-)" + re.escape(wrong))
        text, n = pattern.subn(lambda m: m.group(1) + REAL_ADSENSE_PUB, text)
        if n:
            counts[f"adsense:{wrong}"] = n

    for wrong in WRONG_AMAZON_TAGS:
        pattern = re.compile(r"([?&]tag=)" + re.escape(wrong) + r"\b")
        text, n = pattern.subn(lambda m: m.group(1) + REAL_AMAZON_TAG, text)
        if n:
            counts[f"amazon:{wrong}"] = n

    return text, counts


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    changed = refused = 0
    totals: dict[str, int] = {}

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text, counts = normalize(text)
        if not counts:
            continue

        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
        changed += 1

        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            changed -= 1
            print(f"  REFUSED {name}: {exc}")

    # ads.txt must authorize exactly the publisher the pages now serve.
    with open(ADS_TXT, encoding="utf-8") as fh:
        ads = fh.read()
    want = f"google.com, pub-{REAL_ADSENSE_PUB}, DIRECT, f08c47fec0942fa0\n"
    ads_ok = ads.strip() == want.strip()
    if not ads_ok and not dry:
        safe_write_text(ADS_TXT, want)

    print(f"\n{'[dry-run] ' if dry else ''}files changed: {changed} | refused: {refused}")
    for k, v in sorted(totals.items()):
        print(f"  {k}: {v} replacements")
    print(f"  ads.txt: {'already correct' if ads_ok else ('would rewrite' if dry else 'rewritten')}")
    print(f"\n  AdSense publisher -> ca-pub-{REAL_ADSENSE_PUB}")
    print(f"  Amazon tag        -> {REAL_AMAZON_TAG}")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
