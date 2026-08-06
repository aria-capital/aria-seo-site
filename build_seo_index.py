"""
build_seo_index.py
Regenerates all-articles.html and sitemap.xml from the files on disk.
Python 3.9 compatible. Run from seo_site/ directory or anywhere.
"""
import os
import re
from datetime import datetime

from safe_write import safe_write_html, safe_write_sitemap

# ── CONFIG ──────────────────────────────────────────────────────────────────
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://aria-capital.github.io/aria-seo-site"
GUMROAD_URL = "https://icunotebook.gumroad.com/"  # update if slug differs
SKIP_FILES = {
    "index.html", "all-articles.html", "about.html", "contact.html",
    "privacy_policy.html", "privacy-policy.html", "affiliate-disclosure.html",
    "dmca-policy.html", "terms-of-service.html",
}

# ── CATEGORY RULES (checked in order; first match wins) ─────────────────────
# Each entry: (category_id, display_label, anchor_id, list_of_keyword_substrings)
CATEGORIES = [
    ("icu", "ICU Clinical Library", "icu-clinical-library", [
        "icu-", "-icu", "abdominal-compartment", "acalculous", "abg-", "vasopressor",
        "precedex", "dexmedetomidine", "propofol-vs", "midazolam", "propofol-sedation",
        "mannitol", "hypertonic-saline", "norepinephrine", "epinephrine-vs",
        "phenylephrine", "labetalol", "nicardipine", "hypertensive-emergency",
        "lactated-ringers", "normal-saline-icu", "4-factor-pcc", "kcentra",
        "refractory-shock", "second-line-agents", "serotonin-syndrome",
        "targeted-temperature-management", "post-cardiac-arrest",
        "warfarin-vs-doac", "iv-magnesium", "calcium-chloride", "calcium-gluconate",
        "12-lead-ekg", "ventilator", "hemodynamic", "cardiac-surgery-icu",
        "vasopressin", "dobutamine", "milrinone", "nimbex", "cisatracurium",
        "snf-sepsis", "clinical-decision-support-icu",
    ]),
    ("crna", "CRNA Path & Schools", "crna-path-schools", [
        "crna", "srna", "aa-vs-crna", "nurse-anesthesia",
    ]),
    ("travel", "Travel Nursing", "travel-nursing", [
        "travel-nurs", "travel-nurse", "shiftkey", "carerev", "shiftmed",
        "per-diem-nurs", "per-diem-nurse", "agency-vs-hospital",
        "night-shift-differential", "baylor-plan", "travel-nursing-complete",
        "travel-nursing-affiliate", "travel-nurse-how-to",
        "nurse-agency", "nurse-union-vs-nonunion",
        "amn-vs-aya", "aya-vs-vivian", "vivian-health", "clipboard-health",
    ]),
    ("nclex", "NCLEX Prep", "nclex-prep", [
        "nclex",
    ]),
    ("ai", "Healthcare & Business AI", "healthcare-ai", [
        "ai-clinical", "clinical-decision-support", "best-medical-ai",
        "ai-scribe", "abridge", "ai-bookkeeping", "ai-content-creation",
        "ai-customer-service", "ai-email-writing", "best-ai-tools",
        "canva-ai", "chatgpt-vs-claude", "notion-ai", "building-one-person-business",
        "automate-social-media-with-ai", "ai-medical-scribe",
    ]),
    ("nurse-finance", "Nurse Money & Taxes", "nurse-money-taxes", [
        "nurse-invest", "nurse-403b", "nurse-salary", "nurse-student-loan",
        "nurse-pslf", "nurse-credit", "nurse-emergency-fund", "nurse-net-worth",
        "nurse-home-buy", "nurse-health-insurance", "nurse-retire",
        "nurse-passive-income", "nurse-side-hustle", "nurse-robo",
        "nurse-target-date", "nurse-three-fund", "nurse-treasury",
        "nurse-sinking", "nurse-rebalanc", "nurse-burnout-financial",
        "nurse-financial-freedom", "403b-vs-457b-nurse", "403b-vs-457b",
        "nurse-financial", "article-nurse-403b", "article-nurse-credit",
        "article-nurse-emergency", "article-nurse-home", "article-nurse-invest",
        "article-nurse-net-worth", "article-nurse-passive", "article-nurse-retire",
        "article-nurse-salary", "article-nurse-side-hustle", "article-nurse-student",
        "article-night-shift", "article-per-diem", "article-hospital-nurse",
        "article-icu-nurse-burn", "article-icu-nurse-overtime",
        "article-new-grad-nurse", "article-agency-vs", "article-rn-to-bsn",
        "article-nursing-license", "article-nursing-specialty",
        "nurse-pslf-guide", "nurse-student-loan-forgiveness",
        "nurse-staffing-ratio", "nurse-delegation", "hospital-nurse-overtime",
        "va-nurse-pay", "nurse-union", "new-grad-rn-salary", "np-salary",
        "rn-malpractice",
    ]),
    ("personal-finance", "Personal Finance", "personal-finance", [
        "compound-interest", "credit-score", "etf-vs-mutual", "high-yield-savings",
        "index-fund-invest", "nurse-index-fund", "50-30-20", "zero-based-budgeting",
        "debt-avalanche", "budgeting-for-irregular", "emergency-fund",
        "renting-vs-buying", "home-buying", "side-hustle-tax", "pay-off-student",
        "article-compound", "article-credit-card", "article-debt-avalanche",
        "article-emergency-fund", "article-first-invest", "article-freelance-rates",
        "article-high-yield", "article-home-buying", "article-no-spend",
        "article-renting-vs", "article-side-hustle-tax", "article-remote-jobs",
        "article-work-from-home", "article-declutter",
        "credit-score-improvement", "pay-off-student-loans",
        "budgeting-apps", "roth-ira", "how-to-start-investing",
        "how-to-negotiate-salary", "freelancing-taxes",
        "article-linkedin-profile",
    ]),
    ("side-hustle", "Side Hustles & Passive Income", "side-hustles-passive-income", [
        "side-hustle", "passive-income", "side-income", "teachers-pay-teachers",
        "iv-hydration-business", "nurse-etsy", "nurse-online-teaching",
        "icu-nurse-side-hustle", "nurse-burnout-financial-recovery",
        "declutter-to-make-money", "remote-jobs", "work-from-home-productivity",
        "article-declutter", "article-remote", "article-work-from-home",
        "ebay-arbitrage", "defi-yield", "how-to-self-publish",
        "amazon-kdp-for-beginners",
    ]),
    ("pets", "Pets", "pets", [
        "dog-", "-dog-", "cat-", "-cat-", "pet-", "-pet-", "puppy",
        "article-dog", "article-cat", "article-pet", "article-new-puppy",
        "article-best-dog", "veterinar", "vet-visit",
    ]),
    ("fitness", "Health & Fitness", "health-fitness", [
        "fitness", "workout", "gym-", "-gym", "yoga", "sleep-optim",
        "meal-prep", "protein-intake", "intermittent-fasting", "strength-training",
        "walking-for-weight", "progressive-overload", "habit-tracking",
        "morning-routine", "home-workout", "stress-management",
        "30-day-fitness", "article-cheapest-ways-to-get-fit",
        "article-gym-vs-home", "article-healthy-meal-prep",
        "article-shift-worker-fitness",
    ]),
    ("gear", "Gear, Journals & Planners", "gear-journals-planners", [
        "stethoscope", "compression-socks", "badge-reel", "nursing-bag",
        "nurse-badge", "nursing-gear", "nurse-self-care",
        "dog-training-log", "home-workout-log",
        "best-journals", "best-log-books", "best-planners",
        "best-wellness-journal",
    ]),
    ("nursing-careers", "Nursing Careers & Clinical Guides", "nursing-careers", [
        # catch-all for nursing articles not caught above
        "nurs", "rn-to", "bsn-", "absn-", "lpn", "cna-",
        "nurse-", "nursing-", "oncolog", "pediatric", "pacu",
        "picu", "sicu", "trauma-nurse", "or-nurse", "postpartum",
        "obstetric", "cardiac-", "telemetry", "stepdown", "step-down",
        "occupational-health-nurse", "public-health-nurse",
        "school-nurse", "telehealth-nurs", "telephone-triage",
        "utilization-review-nurse", "virtual-nurs", "wound-care-nurs",
        "medication-administration", "nursing-diagnosis", "nursing-documentation",
        "vital-signs-nurs", "respiratory-assessment", "pain-assessment",
        "pain-management-nurs", "seizure-nurs", "sepsis-nurs", "stroke-nurs",
        "shock-nurs", "pneumonia-nurs", "renal-failure-nurs",
        "pulmonary-embolism", "transfusion-reaction", "sickle-cell-nurs",
        "spinal-cord-injury", "traumatic-brain-injury-nurs",
        "rapid-response", "triage-nurs", "ostomy-nurs", "oxygen-therapy",
        "tracheostomy", "pressure-injur", "wound-assess", "phlebotomy-nurs",
        "peripheral-arterial", "preeclampsia", "postoperative-nurs",
        "perioperative", "post-op-complication", "orthopedic-nurs",
        "ccrn", "dnp-", "np-specialties", "how-to-get-into-np",
        "second-career-nursing", "new-grad-rn-job", "respiratory-therapist",
    ]),
]

FALLBACK_CATEGORY = ("other", "Other Articles", "other-articles")


def slug_to_title(filename):
    """Convert article-some-slug-2026.html -> Article Some Slug"""
    name = filename.replace(".html", "")
    # Remove year suffixes like -2026
    name = re.sub(r"-20\d\d$", "", name)
    # Remove leading "article-" prefix
    name = re.sub(r"^article-", "", name)
    words = name.replace("-", " ").replace("_", " ").split()
    # Title-case with common acronym preservation
    acronyms = {"icu", "crna", "rn", "bsn", "lpn", "cna", "np", "dnp", "picu",
                "sicu", "pacu", "or", "ai", "kdp", "etf", "iv", "ekg", "ccu",
                "srna", "pcc", "doac", "va", "pslf", "icp", "ards", "vte",
                "ppe", "ceu", "sbar", "pca", "snf", "abg", "nms", "hellp",
                "tbi", "pe", "pca"}
    result = []
    for w in words:
        if w.lower() in acronyms:
            result.append(w.upper())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def categorize(filename):
    slug = filename.lower()
    for cat_id, label, anchor, keywords in CATEGORIES:
        for kw in keywords:
            if kw in slug:
                return cat_id, label, anchor
    return FALLBACK_CATEGORY


def get_all_articles():
    articles = []
    for f in sorted(os.listdir(SITE_DIR)):
        if not f.endswith(".html"):
            continue
        if f in SKIP_FILES:
            continue
        # Skip hub files and wire files
        if f.endswith("-hub.html") or f.endswith("-hub-2026.html"):
            continue
        if f.startswith("_"):
            continue
        articles.append(f)
    return articles


def build_all_articles_html(articles):
    # Group by category
    cat_map = {}  # cat_id -> (label, anchor, [filenames])
    for filename in articles:
        cat_id, label, anchor = categorize(filename)
        if cat_id not in cat_map:
            cat_map[cat_id] = (label, anchor, [])
        cat_map[cat_id][2].append(filename)

    # Preserve preferred category order
    cat_order = [c[0] for c in CATEGORIES] + [FALLBACK_CATEGORY[0]]

    total = len(articles)
    now = datetime.utcnow().strftime("%B %Y")

    # Build TOC entries
    toc_links = []
    sections = []

    for cat_id in cat_order:
        if cat_id not in cat_map:
            continue
        label, anchor, files = cat_map[cat_id]
        count = len(files)
        toc_links.append(
            f'<a href="#{anchor}">{label} ({count})</a>'
        )
        items = "\n".join(
            f'<li><a href="{fn}">{slug_to_title(fn)}</a></li>'
            for fn in files
        )
        sections.append(
            f'<h2 id="{anchor}">{label} <span class="count">({count})</span></h2>\n'
            f'<ul>\n{items}\n</ul>'
        )

    toc_html = "\n".join(toc_links)
    sections_html = "\n\n".join(sections)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All Articles — Complete Index of {total} Guides | ARIA Capital Holdings LLC</title>
<meta name="description" content="Browse all {total} guides covering ICU clinical references, CRNA school comparisons, travel nurse pay and taxes, nurse investing, side hustles, personal finance, pets, and fitness — updated {now}.">
<link rel="canonical" href="{BASE_URL}/all-articles.html">
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
.toc{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-top:24px;font-size:0.92em;line-height:2.2}}
.toc a{{color:#16213e;margin-right:14px;text-decoration:none}}
.toc a:hover{{color:#22c55e}}
footer{{background:#111;color:#6b7280;padding:20px;text-align:center;font-size:0.85em;margin-top:48px}}
footer a{{color:#9ca3af;text-decoration:none}}
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>ARIA Capital Holdings LLC</h1>
    <p>Nurse finance, ICU clinical references, travel nursing, investing &amp; side hustles</p>
  </div>
</header>
<nav>
  <div class="container">
    <a href="index.html">Home</a>
    <a href="all-articles.html">All Articles</a>
    <a href="icu-emergencies-hub-2026.html">ICU Library</a>
    <a href="travel-nurse-hub-2026.html">Travel Nursing</a>
    <a href="nurse-side-hustle-hub-2026.html">Side Hustles</a>
    <a href="how-to-become-a-crna-2026.html">CRNA Path</a>
    <a href="about.html">About</a>
    <a href="privacy_policy.html">Privacy</a>
  </div>
</nav>
<div class="container">
  <h1 style="font-size:1.6em;margin:28px 0 6px;">All {total} Articles</h1>
  <p style="color:#6b7280;font-size:0.95em;">Every guide published on this site — ICU clinical references, nurse salary &amp; taxes, travel nursing, side hustles, pets, fitness, and more. Updated {now}.</p>
  <div class="toc">
    <strong>Jump to:</strong><br>
    {toc_html}
  </div>

{sections_html}

</div>
<footer>
  <p>
    &copy; 2026 ARIA Capital Holdings LLC &nbsp;|&nbsp;
    <a href="index.html">Home</a> &nbsp;|&nbsp;
    <a href="privacy_policy.html">Privacy Policy</a> &nbsp;|&nbsp;
    <a href="affiliate-disclosure.html">Affiliate Disclosure</a> &nbsp;|&nbsp;
    <a href="https://gumroad.com/l/aria-capital" target="_blank" rel="noopener">Shop on Gumroad</a>
  </p>
  <p style="margin-top:8px;font-size:0.8em;">Guides for nurses, by a nurse-investor. Real numbers, no fluff.</p>
</footer>
</body>
</html>"""
    return html


def build_sitemap_xml(articles):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    urls = []
    # Include the main pages first
    for page in ["index.html", "all-articles.html", "about.html"]:
        urls.append(f"  <url><loc>{BASE_URL}/{page}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>")
    # All articles
    for fn in articles:
        urls.append(f"  <url><loc>{BASE_URL}/{fn}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>")

    url_block = "\n".join(urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_block}
</urlset>"""


def main():
    articles = get_all_articles()
    print(f"Found {len(articles)} article files.")

    # Write all-articles.html
    html = build_all_articles_html(articles)
    out_html = os.path.join(SITE_DIR, "all-articles.html")
    safe_write_html(out_html, html)
    print(f"Written: {out_html}")

    # Write sitemap.xml
    xml = build_sitemap_xml(articles)
    out_xml = os.path.join(SITE_DIR, "sitemap.xml")
    safe_write_sitemap(out_xml, xml)
    print(f"Written: {out_xml}")
    print(f"Sitemap contains {len(articles) + 3} URLs (articles + 3 main pages).")
    print("Done. Review files, then run PUSH_SEO_FULL.bat.")


if __name__ == "__main__":
    main()
