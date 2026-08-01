#!/usr/bin/env python3
"""
normalize_monetization_ids.py — make every page use the ONE real AdSense publisher
and the ONE real Amazon Associates tag.

WHY THIS EXISTS
Two monetization identities drifted into the corpus, and in both cases the wrong one won.

AdSense
    ads.txt authorizes  pub-6510170611627184
    all 1,460 pages served ca-pub-5576001602612111

    ads.txt is the authorized-sellers file: it declares which publisher may sell ad
    inventory on this domain. Ad code running under a publisher ID that ads.txt does not
    list reads as unauthorized inventory, and demand does not bid on it.

    Provenance (git):
      ca91ea4 2026-07-13  "Add AdSense ca-pub-6510170611627184 to all pages"   <- deliberate
      08ca615 2026-07-17  "Add ads.txt for AdSense verification"  (same ID)     <- deliberate
      b93bf9f 2026-07-21  1453-article bulk generation             (5576...)    <- introduced
                          ...and did NOT touch ads.txt.
    A genuine account change updates both the pages and ads.txt. A generator emitting a
    templated ID updates only what it generates. 6510... is the real account.

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
REAL_ADSENSE_PUB = "6510170611627184"
REAL_AMAZON_TAG = "ariacapital-20"

WRONG_ADSENSE_PUBS = ["5576001602612111"]
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
