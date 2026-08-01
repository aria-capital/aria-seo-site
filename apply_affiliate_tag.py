#!/usr/bin/env python3
"""
apply_affiliate_tag.py — Monetize the SEO affiliate site in one command.

WHY THIS EXISTS
    Every outbound Amazon link on the site is a bare search URL
    (https://amazon.com/s?k=...) with NO Amazon Associates tag. Without the
    tag, Amazon pays $0 commission even when a reader clicks and buys.
    This is the single biggest thing blocking the SEO site from earning.

WHAT IT DOES
    - Reads AMAZON_ASSOCIATE_TAG from the environment or ../.env.aria
    - Normalizes every Amazon href to https://www.amazon.com (bare amazon.com
      can drop the tag on redirect)
    - Appends &tag=<your-tag>-20 to every Amazon link across all *.html files
    - Idempotent: never double-adds a tag; safe to run repeatedly
    - Dry-run by default. Pass --apply to actually write changes.

USAGE
    python3 apply_affiliate_tag.py            # report: how many links, tag status
    python3 apply_affiliate_tag.py --apply    # tag every Amazon link (needs tag set)

TO ACTIVATE (Carlos, one-time):
    1. Get your tag at https://affiliate-program.amazon.com  (looks like name-20)
    2. Add this line to .env.aria:   AMAZON_ASSOCIATE_TAG=yourtag-20
    3. Run:  python3 seo_site/apply_affiliate_tag.py --apply
    From then on, every Amazon link on the site earns commission.
"""
import os
import re
import sys
from pathlib import Path

from safe_write import safe_write_html

SITE_DIR = Path(__file__).resolve().parent
ENV_FILE = SITE_DIR.parent / ".env.aria"

# Matches the href value of any Amazon link, capturing the URL.
AMAZON_HREF = re.compile(r'href="(https?://(?:www\.)?amazon\.com/[^"]*)"', re.I)


def load_tag() -> str:
    """Return the Amazon Associates tag from env or .env.aria, or ''."""
    tag = os.environ.get("AMAZON_ASSOCIATE_TAG", "").strip()
    if not tag and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("AMAZON_ASSOCIATE_TAG=") and not line.startswith("#"):
                tag = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    # Reject obvious placeholders
    if tag.lower() in {"", "yourtag-20", "your-tag", "your_tag_here", "name-20"}:
        return ""
    return tag


def tag_url(url: str, tag: str) -> str:
    """Normalize host to www and add tag=... if not already present."""
    url = re.sub(r'^https?://(?:www\.)?amazon\.com', 'https://www.amazon.com', url, flags=re.I)
    if re.search(r'[?&]tag=', url):
        return url  # already tagged — idempotent
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}tag={tag}"


def main() -> int:
    apply = "--apply" in sys.argv
    tag = load_tag()

    html_files = sorted(SITE_DIR.glob("*.html"))
    total_links = 0
    already_tagged = 0
    files_with_links = 0
    changed_files = 0

    for f in html_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        links = AMAZON_HREF.findall(text)
        if not links:
            continue
        files_with_links += 1
        total_links += len(links)
        already_tagged += sum(1 for u in links if re.search(r'[?&]tag=', u))

        if apply and tag:
            new_text = AMAZON_HREF.sub(
                lambda m: f'href="{tag_url(m.group(1), tag)}"', text)
            if new_text != text:
                safe_write_html(str(f), new_text, allow_preexisting=True)
                changed_files += 1

    untagged = total_links - already_tagged
    print("=" * 56)
    print(" ARIA — Amazon Affiliate Tag Applier")
    print("=" * 56)
    print(f" HTML files scanned      : {len(html_files)}")
    print(f" Files with Amazon links : {files_with_links}")
    print(f" Amazon links total      : {total_links}")
    print(f" Already tagged          : {already_tagged}")
    print(f" Untagged (earning $0)   : {untagged}")
    print(f" Associate tag configured: {'YES (' + tag + ')' if tag else 'NO — set AMAZON_ASSOCIATE_TAG in .env.aria'}")
    print("-" * 56)
    if not tag:
        print(" ACTION NEEDED: add AMAZON_ASSOCIATE_TAG=yourtag-20 to .env.aria,")
        print("               then run:  python3 seo_site/apply_affiliate_tag.py --apply")
        return 0
    if apply:
        print(f" APPLIED. Files rewritten: {changed_files}. All Amazon links now tagged '{tag}'.")
    else:
        print(f" DRY-RUN. Would tag {untagged} links with '{tag}'. Re-run with --apply to write.")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
