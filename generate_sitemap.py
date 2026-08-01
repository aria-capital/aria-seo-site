#!/usr/bin/env python3
"""Regenerate sitemap.xml + robots.txt for the SEO site from the current .html files.

Run this any time articles are added. It replaces the hand-maintained sitemap that
was drifting out of date (last drift: 36 articles missing from the index -> not
crawled by Google). Base URL is read from _config.yml so it stays in sync.

Usage:  python generate_sitemap.py
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from safe_write import safe_write_sitemap, safe_write_text

HERE = Path(__file__).resolve().parent

# Low-priority static pages get a different changefreq/priority.
STATIC_LOW = {"about.html", "affiliate-disclosure.html", "privacy.html", "contact.html"}
# Files that should never appear in the sitemap.
EXCLUDE = {"404.html", "google-verify.html"}


def read_base_url() -> str:
    """
    Build the canonical base URL from _config.yml (url + baseurl).

    Raises if _config.yml has no usable `url:`. This used to fall back to
    "https://carlostrujillo.github.io" — a host the site has never been served from; the
    org was renamed to aria-capital in July 2026 and the old username is dead for Pages.
    A missing or reshaped config would therefore have written 1,461 <loc> entries pointing
    at a domain that does not resolve, and nothing would have caught it: the integrity
    check only verifies that each <loc>'s slug maps to a real local file, which stays true
    no matter which host is in front of it. Failing loudly is the only safe default.
    """
    url, baseurl = "", ""
    cfg = HERE / "_config.yml"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^url:\s*(\S+)", text, re.M)
        if m:
            url = m.group(1).strip().rstrip("/")
        m = re.search(r"^baseurl:\s*(\S+)", text, re.M)
        if m:
            baseurl = m.group(1).strip().strip('"').strip("'")
    if not url:
        raise SystemExit(
            f"Refusing to build a sitemap: no 'url:' in {cfg}. Every <loc> would point at "
            "a guessed host, and no check downstream would notice."
        )
    if baseurl and not baseurl.startswith("/"):
        baseurl = "/" + baseurl
    return f"{url}{baseurl}".rstrip("/") + "/"


def build() -> tuple[int, str]:
    base = read_base_url()
    html_files = sorted(
        p.name for p in HERE.glob("*.html") if p.name not in EXCLUDE
    )

    rows: list[str] = []
    for name in html_files:
        mtime = datetime.fromtimestamp(
            (HERE / name).stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        if name == "index.html":
            loc = base  # homepage = clean root URL
            changefreq, priority = "weekly", "1.0"
        elif name in STATIC_LOW:
            loc = base + name
            changefreq, priority = "yearly", "0.3"
        else:
            loc = base + name
            changefreq, priority = "monthly", "0.8"
        rows.append(
            f"  <url><loc>{loc}</loc><lastmod>{mtime}</lastmod>"
            f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        )

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )
    safe_write_sitemap(str(HERE / "sitemap.xml"), sitemap)

    robots = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {base}sitemap.xml\n"
    )
    safe_write_text(str(HERE / "robots.txt"), robots)

    return len(html_files), base


if __name__ == "__main__":
    n, base = build()
    print(f"sitemap.xml regenerated: {n} URLs | base={base}")
    print("robots.txt written")
