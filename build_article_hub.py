#!/usr/bin/env python3
"""Generate all-articles.html — a complete, categorized hub linking EVERY article.

Why: 2026-07-04 audit found index.html carries only ~300 cards while 712 articles
exist on disk — ~380 pages had ZERO internal links from the homepage (orphans).
This hub guarantees every page is one click from the nav. Re-run after adding
articles (PUSH_FRESH.py flow: run this, then generate_sitemap.py, then push).

Usage: python build_article_hub.py
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCLUDE = {"index.html", "all-articles.html", "404.html", "google-verify.html",
           "about.html", "contact.html", "privacy-policy.html", "privacy.html",
           "terms-of-service.html", "dmca-policy.html", "affiliate-disclosure.html"}

# Ordered rules: first match wins. (pattern on slug, category)
RULES = [
    (r"icu-nurses-2026|^icu-|^ecmo|^ventilator|^vv-vs-va|^push-dose|^prone-|^lung-protective|^peep-|^crrt|^iabp|^impella|^swan-ganz", "ICU Clinical Library"),
    (r"crna", "CRNA Path & Schools"),
    (r"travel-nurse|clipboard|vivian|amn-vs|^best-travel-nurse|furnished-finder|gsa-rates|per-diem-vs-staff", "Travel Nursing"),
    (r"nclex", "NCLEX Prep"),
    (r"ai-scribe|ai-medical-scribe|abridge|suki|deepscribe|nabla|heidi|freed|sunoh|tali|ambience", "Healthcare AI"),
    (r"roth|403b|457b|529|solo-401k|hsa|fire-number|financial|retirement|estate|insurance|mortgage|tax|paycheck|invest|backdoor|idr|w4|quarterly|sign-on-bonus|emergency-fund|budget|credit-card|negotiate|salary|differential|overtime|money", "Nurse Money & Taxes"),
    (r"best-journal|best-planner|best-log-book|best-notebook|best-scrub|best-shoe|best-stethoscope|best-gift|best-wellness|study-journal", "Gear, Journals & Planners"),
    (r"kdp|passive-income|etsy|side-hustle|ebay|blog|influencer|entrepreneur|coaching|consulting|curriculum|defi|social-media", "Side Hustles & Passive Income"),
    (r"nurse|nursing|charge|preceptor|magnet|staffing|telehealth|informatics|float-pool|case-management|night-shift|med-surg|new-grad|resume|linkedin|burnout|sepsis", "Nursing Careers"),
]

def title_of(p: Path) -> str:
    m = re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8", errors="replace")[:4000], re.S)
    t = re.sub(r"\s+", " ", m.group(1)).strip() if m else p.stem.replace("-", " ").title()
    return t.split(" | ")[0].split(" — Money Psychology")[0]

def cat_of(slug: str) -> str:
    for pat, cat in RULES:
        if re.search(pat, slug):
            return cat
    return "More Guides"

def main() -> None:
    cats: dict[str, list[tuple[str, str]]] = {}
    files = sorted(x for x in HERE.glob("*.html") if x.name not in EXCLUDE)
    for f in files:
        cats.setdefault(cat_of(f.name), []).append((f.name, title_of(f)))
    order = [c for _, c in RULES] + ["More Guides"]
    seen, ordered = set(), []
    for c in order:
        if c in cats and c not in seen:
            ordered.append(c); seen.add(c)
    n = len(files)
    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All Articles — Complete Index of {n} Guides | Money Psychology</title>
<meta name="description" content="Browse all {n} guides: ICU clinical references, CRNA school comparisons, travel nurse pay and taxes, nurse investing, side hustles, and more.">
<link rel="canonical" href="https://aria-capital.github.io/aria-seo-site/all-articles.html">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Georgia",serif;color:#1a1a2e;background:#fafafa;line-height:1.7}}
header{{background:#1a1a2e;color:#fff;padding:20px 0}}
.container{{max-width:960px;margin:0 auto;padding:0 20px}}
header h1{{font-size:1.8em;letter-spacing:1px}}
header p{{color:#9ca3af;font-size:0.95em;margin-top:4px}}
nav{{background:#16213e;padding:10px 0}}
nav a{{color:#9ca3af;text-decoration:none;margin-right:20px;font-size:0.9em}}
nav a:hover{{color:#fff}}
h2{{font-size:1.3em;margin:36px 0 12px;padding-bottom:8px;border-bottom:2px solid #22c55e}}
ul{{list-style:none}}
li{{padding:5px 0;border-bottom:1px solid #eee;font-size:0.95em}}
li a{{color:#16213e;text-decoration:none}}
li a:hover{{color:#22c55e;text-decoration:underline}}
.count{{color:#6b7280;font-size:0.85em;font-weight:normal}}
.toc{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-top:24px;font-size:0.92em}}
.toc a{{color:#16213e;margin-right:14px;text-decoration:none}}
.toc a:hover{{color:#22c55e}}
footer{{background:#111;color:#6b7280;padding:20px;text-align:center;font-size:0.85em;margin-top:48px}}
footer a{{color:#9ca3af;text-decoration:none}}
</style>
</head>
<body>
<header><div class="container"><h1>Money Psychology</h1><p>Build income while you sleep</p></div></header>
<nav><div class="container"><a href="index.html">Home</a><a href="all-articles.html">All Articles</a><a href="about.html">About</a><a href="affiliate-disclosure.html">Disclosure</a></div></nav>
<div class="container">
<h1 style="margin-top:32px;font-size:1.7em">All Articles</h1>
<p style="color:#6b7280;margin-top:6px">Every guide on the site — {n} articles, updated {date.today().isoformat()}.</p>
<div class="toc">"""]
    for c in ordered:
        anchor = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
        parts.append(f'<a href="#{anchor}">{c} ({len(cats[c])})</a>')
    parts.append("</div>")
    for c in ordered:
        anchor = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
        parts.append(f'<h2 id="{anchor}">{c} <span class="count">({len(cats[c])})</span></h2>\n<ul>')
        for slug, title in sorted(cats[c], key=lambda x: x[1].lower()):
            parts.append(f'<li><a href="{slug}">{title}</a></li>')
        parts.append("</ul>")
    parts.append("""</div>
<footer><a href="index.html">Home</a> · <a href="about.html">About</a> · <a href="privacy-policy.html">Privacy</a> · <a href="terms-of-service.html">Terms</a> · <a href="affiliate-disclosure.html">Affiliate Disclosure</a></footer>
</body>
</html>""")
    out = HERE / "all-articles.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out.name}: {n} articles in {len(ordered)} categories")
    for c in ordered:
        print(f"  {c}: {len(cats[c])}")

if __name__ == "__main__":
    main()
