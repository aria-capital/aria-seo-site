#!/usr/bin/env python3
"""
build_curated_sitemap.py — a sitemap that advertises a curated subset, not the whole corpus.

WHY THIS EXISTS
The site matches three of Google's four scaled-content-abuse triggers. Submitting all 1,461
URLs at once is manual-action bait; the plan of record (plan-30-days-20260728) calls for a
curated sitemap of roughly 934 URLs instead, expanded in batches once indexing looks clean.

Crucially, this does NOT remove pages from the site. Every article stays live and reachable.
It only changes what is advertised to crawlers.

WHY NOT THE EXISTING QUARANTINE LIST
seo_quarantine.json holds 736 entries and looks authoritative. It is not usable as a quality
signal, for two measured reasons:

  * The gate's floor is SEO_FLOOR = 9 and the highest score any article has ever achieved
    is 7, so every article fails by construction. 437 of the 736 scored 5 — the best band
    actually observed — and were quarantined anyway.
  * 113 entries carry score 1, the exact signature of a Groq API failure. The scorer returns
    1/1/1/1 on any exception and the persisted record drops the error field, so a crash is
    indistinguishable from a measurement.

Cutting 736 pages on that basis would remove the strongest articles on record because a
threshold nobody can reach was set too high.

WHAT THIS USES INSTEAD
Body word count, measured after stripping script/style/nav/footer/form. It is observable,
reproducible, and is the property Google actually describes when it talks about thin content.
Measured across the corpus: median 1,111 words, p10 791, minimum 287 — only 32 articles fall
under 600 words, which is itself the finding that the corpus is not thin.

Selection, in order:
  1. exclude meta/utility pages (they are linked, not indexed as content)
  2. exclude anything under MIN_WORDS — genuinely thin
  3. rank the remainder by body word count and take the top TARGET

USAGE
    python3 build_curated_sitemap.py --dry-run
    python3 build_curated_sitemap.py
    python3 build_curated_sitemap.py --target 1200     # widen a batch later
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date

from generate_sitemap import read_base_url
from safe_write import safe_write_sitemap

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sitemap.xml")

TARGET = 934          # the plan of record's batch-1 size
MIN_WORDS = 600       # below this an article reads as thin regardless of ranking

# Linked from every page; they belong in the sitemap as navigation, not as ranked content.
#
# 2026-09-02: the six HUB pages were added here after Search Console measurement showed the
# ranker had split them. Hubs are ranked by body word count like any article, and two of the
# six fell below the batch-1 cut — so `icu-devices-hub-2026.html` and `federal-nurse-hub-2026.html`
# were left out of the sitemap AND given `noindex, follow` by apply_noindex_to_uncurated.py,
# while both remained linked from the homepage as primary navigation. Google's live URL
# inspection returned "Excluida por una etiqueta noindex" for them on 2026-09-02.
# A hub is structure, not content: it is the only discovery path to its cluster, so its word
# count is the wrong property to rank it on. They belong here, with the other navigation.
CORE_PAGES = [
    "", "about.html", "contact.html", "privacy-policy.html",
    "affiliate-disclosure.html", "terms-of-service.html",
    "icu-emergencies-hub-2026.html", "icu-devices-hub-2026.html",
    "icu-pharmacology-hub-2026.html", "crna-career-hub-2026.html",
    "federal-nurse-hub-2026.html", "travel-nurse-hub-2026.html",
]
META = {
    "index.html", "about.html", "contact.html", "privacy-policy.html", "privacy.html",
    "affiliate-disclosure.html", "terms-of-service.html", "dmca-policy.html",
    "all-articles.html", "404.html", "google-verify.html", "start-here.html",
}

_STRIP = re.compile(r"(?is)<(script|style|nav|footer|form)[^>]*>.*?</\1>")
_TAGS = re.compile(r"(?s)<[^>]+>")


def body_words(html: str) -> int:
    """Words of actual article prose, with chrome removed."""
    text = _STRIP.sub(" ", html)
    return len(re.sub(r"\s+", " ", _TAGS.sub(" ", text)).strip().split())


def select(target: int = TARGET, min_words: int = MIN_WORDS) -> tuple[list[str], dict]:
    scored: list[tuple[str, int]] = []
    thin: list[str] = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html") or name in META:
            continue
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
            words = body_words(fh.read())
        (thin if words < min_words else scored).append(name if words < min_words else (name, words))

    scored.sort(key=lambda r: -r[1])
    chosen = [n for n, _ in scored[:target]]
    stats = {
        "articles": len(scored) + len(thin),
        "thin_excluded": len(thin),
        "eligible": len(scored),
        "selected": len(chosen),
        "held_back": max(0, len(scored) - target),
        "min_words_selected": scored[len(chosen) - 1][1] if chosen else 0,
    }
    return sorted(chosen), stats


def build_xml(names: list[str], base: str) -> str:
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in CORE_PAGES:
        lines.append(f"  <url><loc>{base}{page}</loc><lastmod>{today}</lastmod>"
                     f"<changefreq>monthly</changefreq><priority>0.5</priority></url>")
    # 2026-09-02: dedupe. CORE_PAGES used to hold only meta pages, which the ranker skips via
    # META, so nothing could collide. Adding the hubs here broke that assumption — four of the
    # six also rank into `names`, and this loop would have emitted them a second time. A sitemap
    # with duplicate <loc> entries is exactly the kind of malformation that costs a crawler's
    # trust, and nothing downstream was checking for it.
    core = set(CORE_PAGES)
    for name in names:
        if name in core:
            continue
        lines.append(f"  <url><loc>{base}{name}</loc><lastmod>{today}</lastmod>"
                     f"<changefreq>monthly</changefreq><priority>0.8</priority></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> int:
    dry = "--dry-run" in sys.argv
    target = TARGET
    if "--target" in sys.argv:
        target = int(sys.argv[sys.argv.index("--target") + 1])

    names, stats = select(target)
    base = read_base_url()
    xml = build_xml(names, base)

    print(f"  articles scanned      : {stats['articles']}")
    print(f"  excluded as thin      : {stats['thin_excluded']}  (under {MIN_WORDS} body words)")
    print(f"  eligible              : {stats['eligible']}")
    print(f"  selected for batch 1  : {stats['selected']}  (+{len(CORE_PAGES)} core pages)")
    print(f"  held back for later   : {stats['held_back']}")
    print(f"  weakest selected      : {stats['min_words_selected']} words")
    print(f"  base URL              : {base}")

    if dry:
        print("\n[dry-run] sitemap.xml not written.")
        return 0

    # The only caller allowed to pass this. See safe_write.safe_write_sitemap.
    safe_write_sitemap(OUT, xml, curated=True)
    # Count what was WRITTEN, not what was intended. Until 2026-09-02 this printed
    # len(names) + len(CORE_PAGES), which stopped being the truth the moment the two lists
    # could overlap: it said 946 over a file holding 942. A summary line that is computed
    # rather than measured is the oldest way an honest script starts lying.
    written = xml.count("<loc>")
    print(f"\n  wrote {OUT} — {written} URLs")
    print("  Every article remains live; this only changes what is advertised to crawlers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
