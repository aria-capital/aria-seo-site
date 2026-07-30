#!/usr/bin/env python3
"""
seo_index_sync.py — Guarantee zero orphaned articles in the SEO site.

WHY THIS EXISTS
---------------
company_auditor.py periodically flags "HTML files: N | Index cards: M — mismatch"
for seo_site. That means articles were written to disk but never linked from
index.html, so search crawlers and readers can't reach them. Over time the gap
grows silently.

This script closes the gap idempotently:
  1. Scans every article *.html in the folder (excluding meta/utility pages).
  2. Finds which ones are NOT already linked from index.html.
  3. Extracts each missing article's <title> + meta description.
  4. Appends card <a> blocks into a dedicated "More Guides" section that lives
     just before the newsletter block, matching the existing card markup.
  5. Rebuilds sitemap.xml to list every article + core pages.

SAFETY
------
- Runs ON THE WINDOWS HOST, where the filesystem is authoritative. Do NOT run it
  from a sandbox with a stale mount — it reads index.html and could act on an old
  copy. (See CLAUDE.md: STALE-BASH-CACHE lesson.)
- Backs up index.html to index.html.bak before writing.
- Only ADDS missing cards; never deletes or reorders existing ones. Safe to run
  repeatedly — a second run adds nothing if nothing is orphaned.

USAGE
-----
    cd C:\\Users\\carlo\\Documents\\PythonScripts\\seo_site
    python seo_index_sync.py            # apply changes
    python seo_index_sync.py --dry-run  # report only, write nothing
"""

from __future__ import annotations
import os
import re
import sys
import html
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
SITEMAP = os.path.join(HERE, "sitemap.xml")
BASE_URL = "https://aria-capital.github.io/aria-seo-site/"

# Pages that are not articles and must never get a card.
META_PAGES = {
    "index.html", "about.html", "affiliate-disclosure.html", "privacy.html",
    "privacy-policy.html", "contact.html", "terms.html", "404.html",
    "start-here.html", "sitemap.html", "disclaimer.html",
}

# Marker comments that bracket the auto-managed section inside index.html.
SECTION_START = "<!-- AUTO:more-guides START -->"
SECTION_END = "<!-- AUTO:more-guides END -->"

# Keyword -> CSS tag class + label. First match wins; order matters.
TAG_RULES = [
    (("crna", "anesthesia", "nurse-anesthet"), ("tag-crna", "CRNA")),
    (("icu-", "-icu-", "ventilator", "sepsis", "abg", "pharmacolog", "drip", "guide-icu"), ("tag-crna", "ICU")),
    (("travel-nurse", "travel-nursing", "stipend", "agenc"), ("tag-travel", "TRAVEL")),
    (("kdp", "log-book", "journal", "self-publish", "amazon"), ("tag-kdp", "KDP")),
    (("passive-income", "side-hustle", "defi", "yield", "dividend"), ("tag-passive", "INCOME")),
    (("salary", "pay", "tax", "loan", "invest", "budget", "money", "financ", "roth", "401k", "403b", "hsa", "credit", "net-worth", "insurance"), ("tag-finance", "FINANCE")),
    (("gear", "shoes", "stethoscope", "gift"), ("tag-gear", "GEAR")),
    (("nurse", "rn", "night-shift", "burnout", "resume", "certification"), ("tag-nursing", "NURSING")),
]
DEFAULT_TAG = ("tag-finance", "GUIDE")


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def article_files() -> list[str]:
    out = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        if name in META_PAGES:
            continue
        out.append(name)
    return out


def linked_in_index(index_html: str) -> set[str]:
    return set(re.findall(r'href="([a-z0-9\-]+\.html)"', index_html))


def extract_title(doc: str, fallback_name: str) -> str:
    m = re.search(r"<title>(.*?)</title>", doc, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        title = html.unescape(m.group(1)).strip()
        # Drop a trailing " — Site Name" style suffix if very long.
        return title
    # Humanize the filename as a last resort.
    stem = fallback_name[:-5].replace("-", " ").title()
    return stem


def extract_desc(doc: str) -> str:
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
                  doc, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        return html.unescape(m.group(1)).strip()
    return "A practical, no-fluff guide for nurses building income and careers."


def pick_tag(name: str) -> tuple[str, str]:
    low = name.lower()
    for keys, tag in TAG_RULES:
        if any(k in low for k in keys):
            return tag
    return DEFAULT_TAG


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def build_card(name: str, title: str, desc: str) -> str:
    tag_class, tag_label = pick_tag(name)
    # Trim description to keep cards even.
    if len(desc) > 240:
        desc = desc[:237].rsplit(" ", 1)[0] + "…"
    return (
        f'      <a class="card" href="{esc(name)}">'
        f'<span class="tag {tag_class}">{esc(tag_label)}</span>'
        f'<h3>{esc(title)}</h3><p>{esc(desc)}</p>'
        f'<div class="read-time">Guide</div></a>'
    )


def build_section(cards: list[str]) -> str:
    inner = "\n".join(cards)
    return (
        f'{SECTION_START}\n'
        f'<div class="section">\n'
        f'  <div class="container">\n'
        f'    <div class="section-title">More Guides</div>\n'
        f'    <div class="grid">\n'
        f'{inner}\n'
        f'    </div>\n'
        f'  </div>\n'
        f'</div>\n'
        f'{SECTION_END}'
    )


def upsert_section(index_html: str, section: str) -> str:
    # Replace an existing auto-section if present (idempotent), else insert
    # before the newsletter block, else before </body>.
    if SECTION_START in index_html and SECTION_END in index_html:
        return re.sub(
            re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END),
            section, index_html, flags=re.DOTALL,
        )
    for anchor in ('<div class="newsletter">', "<footer>", "</body>"):
        idx = index_html.find(anchor)
        if idx != -1:
            return index_html[:idx] + section + "\n\n" + index_html[idx:]
    return index_html + "\n" + section + "\n"


def write_sitemap(all_articles: list[str]) -> int:
    urls = ["", "about.html", "affiliate-disclosure.html"] + all_articles
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        loc = BASE_URL + u
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod></url>")
    lines.append("</urlset>")
    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(urls)


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not os.path.exists(INDEX):
        print(f"ERROR: {INDEX} not found. Run this from the seo_site folder.")
        return 1

    index_html = read(INDEX)
    linked = linked_in_index(index_html)
    articles = article_files()
    missing = [a for a in articles if a not in linked]

    print(f"Article files : {len(articles)}")
    print(f"Already linked: {len(linked & set(articles))}")
    print(f"Orphaned      : {len(missing)}")

    cards = []
    for name in missing:
        try:
            doc = read(os.path.join(HERE, name))
        except OSError:
            continue
        cards.append(build_card(name, extract_title(doc, name), extract_desc(doc)))

    if dry:
        for name in missing:
            print("  + " + name)
        print(f"[dry-run] would add {len(cards)} cards and rewrite sitemap "
              f"({len(articles) + 3} urls). No files written.")
        return 0

    if cards:
        with open(INDEX + ".bak", "w", encoding="utf-8") as f:
            f.write(index_html)
        new_html = upsert_section(index_html, build_section(cards))
        with open(INDEX, "w", encoding="utf-8") as f:
            f.write(new_html)
        print(f"Added {len(cards)} cards to index.html (backup: index.html.bak)")
    else:
        print("No orphaned articles — index.html already complete.")

    n = write_sitemap(articles)
    print(f"Rebuilt sitemap.xml with {n} URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
