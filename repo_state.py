#!/usr/bin/env python3
"""
repo_state.py — print the facts CLAUDE.md asserts, measured from the tree right now.

WHY THIS EXISTS
CLAUDE.md's "Known issues" section has been substantially wrong at the start of three
consecutive sessions. Not through carelessness — it is written as a snapshot and read as
current truth, and the gap between those two things grows every time anything is fixed.
The August 1 session opened with a list where most items were already closed (canonicals,
the AdSense ID, the Amazon tag, index.html) and spent its first hour re-deriving that by
hand. The very next session closed the sitemap item, which made the list stale again
before the ink dried.

The repo's own hard-won lesson is that a guard nobody runs is not a guard. The same is
true of working notes: notes nobody can cheaply verify are not notes, they are folklore.
So this prints the underlying numbers in a couple of seconds. Run it first, read
CLAUDE.md second, and believe this one where they disagree.

This is a REPORTER, not a gate. It never writes, never fails the build, and has no
opinion about whether a number is good. `check_article_corpus.py` and
`check_site_integrity.py` are the gates.

USAGE
    python3 repo_state.py
"""
from __future__ import annotations

import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# Scripts that call safe_write_sitemap() are all capable of rewriting sitemap.xml.
SITEMAP_WRITER = re.compile(r"safe_write_sitemap\s*\(")


def _read(name: str) -> str:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _articles() -> list[str]:
    return sorted(n for n in os.listdir(HERE) if n.endswith(".html"))


def _tracked_fuse_hidden() -> int:
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "ls-files", "-z", ".fuse_hidden*"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return -1
    return len([p for p in out.split("\0") if p])


def sitemap_writers() -> list[str]:
    """Every script that can rewrite sitemap.xml. More than one is a standing hazard."""
    out = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name in ("safe_write.py", "repo_state.py"):
            continue
        if SITEMAP_WRITER.search(_read(name)):
            out.append(name)
    return out


def monetization() -> dict:
    pub, tags, ad_units, loaders = set(), set(), 0, 0
    for name in _articles():
        html = _read(name)
        pub.update(re.findall(r"ca-(pub-\d+)", html))
        tags.update(re.findall(r"[?&]tag=([A-Za-z0-9-]+)", html))
        ad_units += len(re.findall(r'<ins[^>]*class="[^"]*adsbygoogle', html))
        loaders += 1 if "adsbygoogle.js" in html else 0
    return {"publisher_ids": sorted(pub), "amazon_tags": sorted(tags),
            "ad_units": ad_units, "loader_pages": loaders}


def truncated_articles() -> list[str]:
    """
    Articles whose visible text still stops mid-word. These are not structural damage —
    the gates pass on them — so nothing else in the repo will ever report them.
    """
    known = {
        "best-icu-nursing-books-2026.html": "study gui",
        "new-grad-nurse-financial-survival-guide.html": "match captured. Loans",
        "roth-ira-for-nurses-complete-guide.html": "account (don't le",
    }
    return sorted(name for name, fragment in known.items() if fragment in _read(name))


LOCAL_HREF = re.compile(r'href="([^":/?#]+\.html)"')
CONFIG_TITLE = re.compile(r"^title:\s*(.+)$", re.M)
ADS_TXT_PUB = re.compile(r"(pub-[0-9]+)")


def main() -> int:
    articles = _articles()
    sitemap = _read("sitemap.xml")
    money = monetization()
    cut = truncated_articles()
    writers = sitemap_writers()

    card_links = len(set(LOCAL_HREF.findall(_read("index.html"))))
    ads_txt = ADS_TXT_PUB.findall(_read("ads.txt")) or ["no ads.txt"]
    title = CONFIG_TITLE.search(_read("_config.yml"))

    print("corpus")
    print(f"  html files ................. {len(articles)}")
    print(f"  sitemap <loc> entries ...... {sitemap.count('<loc>')}")
    print(f"  index.html card links ...... {card_links}")
    print(f"  tracked .fuse_hidden files . {_tracked_fuse_hidden()}")
    print(f"  still cut off mid-word ..... {len(cut)} {cut or ''}")

    print("\nmonetization (repo evidence only — none of this is account state)")
    print(f"  AdSense publisher ids ...... {money['publisher_ids'] or 'none'}")
    print(f"  ads.txt says ............... {ads_txt}")
    print(f"  Amazon tags ................ {money['amazon_tags'] or 'none'}")
    print(f"  pages with the ad loader ... {money['loader_pages']}")
    note = "   <- a loader with no slots renders nothing" if not money["ad_units"] else ""
    print(f"  actual <ins> ad units ...... {money['ad_units']}{note}")

    print("\nhazards")
    print(f"  scripts that write sitemap.xml: {len(writers)} {writers}")
    if len(writers) > 1:
        print("     more than one writer means last-one-to-run wins; the curated sitemap")
        print("     is a deliberate decision that a legacy writer would silently revert")

    print("\nbrand strings")
    print(f"  _config.yml title .......... {title.group(1) if title else 'none'}")
    for label, needle in (("footers say", "ICU Notebook"), ("also present", "ARIA Capital")):
        n = sum(1 for a in articles if needle in _read(a))
        print(f"  {label:26s} {needle!r} in {n} article(s)")

    print("\nGates are separate: run check_article_corpus.py and check_site_integrity.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
