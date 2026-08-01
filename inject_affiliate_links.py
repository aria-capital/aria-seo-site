"""
inject_affiliate_links.py
ARIA Capital Holdings LLC

Scans all HTML articles in seo_site/, keyword-matches to affiliate programs,
and injects a styled CTA box near the end of each matching file.

IDEMPOTENT: skips files that already contain <!-- AFFILIATE-CTA -->.

Injection priority order:
  1. Before <footer (present in ~1,312 files)
  2. Before </body> (fallback for remaining files)

Usage:
  python inject_affiliate_links.py [--dry-run] [--dir PATH]

  --dry-run   Print what would be changed without writing any files.
  --dir PATH  Override the directory to scan (default: script's own directory).
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime
from typing import List, Tuple, Optional

from check_site_integrity import IntegrityError
from safe_write import safe_write_html, safe_write_text

# ---------------------------------------------------------------------------
# Affiliate definitions
# ---------------------------------------------------------------------------

AFFILIATES = [
    {
        "id": "sofi",
        "name": "SoFi",
        "keywords": [
            "student loan", "student debt", "loan refinanc", "pslf",
            "public service loan forgiveness", "loan forgiveness nurse",
            "nursing school debt", "income-driven repayment", "idr plan",
            "federal student loan", "private student loan", "loan consolidat",
            "parent plus loan", "graduate plus loan", "nurse loan",
        ],
        "cta_text": (
            'Nurses with student loans are leaving thousands on the table. '
            '<a href="https://sofi.com/referral/?via=aria" style="color:#7ec8e3;" '
            'rel="nofollow sponsored" target="_blank">SoFi refinancing</a> offers '
            'competitive rates with no origination fees — takes 2 minutes to check '
            'your rate without affecting your credit score. '
            '<strong style="color:#4a90d9;">Important:</strong> refinancing federal '
            'loans forfeits PSLF eligibility. Confirm your forgiveness path first.'
        ),
    },
    {
        "id": "credible",
        "name": "Credible",
        "keywords": [
            "refinanc", "student loan", "personal loan", "loan comparison",
            "loan rate", "loan interest", "pslf", "debt payoff nurse",
            "consolidate loan", "loan repayment strateg",
        ],
        "cta_text": (
            'Compare real pre-qualified rates from multiple lenders in under '
            '3 minutes — no hard credit pull. '
            '<a href="https://credible.com/partners/?via=aria" style="color:#7ec8e3;" '
            'rel="nofollow sponsored" target="_blank">Check your rate on Credible →</a>'
        ),
    },
    {
        "id": "host_healthcare",
        "name": "Host Healthcare",
        "keywords": [
            "travel nurs", "travel contract", "13-week", "13 week contract",
            "travel rn", "travel icu", "travel nurse pay", "travel nurse agency",
            "travel nurse stipend", "travel nurse housing", "travel nurse tax",
            "best travel nurse agenc", "travel nurse compan",
            "per diem nurs", "local travel nurs",
        ],
        "cta_text": (
            'Looking for your next travel contract? '
            '<a href="https://hosthealthcare.com/?via=aria" style="color:#7ec8e3;" '
            'rel="nofollow sponsored" target="_blank">Host Healthcare</a> is '
            'consistently rated one of the top travel nurse agencies for pay, '
            'support, and housing stipends. Free to apply — a recruiter reaches '
            'out within 24 hours. No commitment required.'
        ),
    },
    {
        "id": "ati_nursing",
        "name": "ATI Nursing",
        "keywords": [
            "nclex", "nclex-rn", "nclex-pn", "nclex prep", "nclex review",
            "nclex study", "nclex question", "nursing certification",
            "certification exam", "ccrn", "cen ", "cnor", "pccn",
            "nursing board exam", "teas exam", "hesi exam",
            "nursing school exam", "pharmacology exam", "nursing exam",
        ],
        "cta_text": (
            'Pass on your first attempt. '
            '<a href="https://atitesting.com/affiliate-program/?via=aria" '
            'style="color:#7ec8e3;" rel="nofollow sponsored" target="_blank">'
            'ATI Nursing Education</a> offers NCLEX prep and certification '
            'review courses trusted by nursing schools nationwide. Use our link '
            'for 5% off your order.'
        ),
    },
    {
        "id": "amazon",
        "name": "Amazon Associates",
        "keywords": [
            "nurs", "hospital", "icu ", "icu nurse", "rn ", " rn,", "bsn", "msn",
            "nursing student", "nursing school", "nursing career",
            "nursing shift", "nursing salary", "bedside nurs",
            "charge nurs", "floor nurs",
        ],
        "cta_text": (
            'Build your clinical reference library: '
            '<a href="https://amazon.com/s?k=nursing+reference+books&tag=ariacapital-20" '
            'style="color:#7ec8e3;" rel="nofollow sponsored" target="_blank">'
            'top-rated nursing textbooks and pocket guides on Amazon →</a> '
            'The Davis\'s Drug Guide and Taber\'s Cyclopedic Medical Dictionary '
            'are the two every bedside nurse should own.'
        ),
    },
]

# Evaluation order matters — more specific affiliates checked first.
# SoFi + Credible can BOTH fire on the same article (they serve different angles).
# The others are mutually exclusive within their category.
LOAN_AFFILIATE_IDS = {"sofi", "credible"}

# ---------------------------------------------------------------------------
# CTA box template
# ---------------------------------------------------------------------------

CTA_TEMPLATE = """\
<!-- AFFILIATE-CTA:{affiliate_id} -->
<div class="affiliate-cta" style="background:#1a1a2e;border:1px solid #4a90d9;padding:1.2em;margin:2em 0;border-radius:6px;">
  <p style="color:#4a90d9;font-weight:bold;margin:0 0 .5em">\U0001f4b0 Recommended Resource</p>
  <p style="color:#e0e0e0;margin:0">{affiliate_text}</p>
</div>
<!-- /AFFILIATE-CTA:{affiliate_id} -->"""

IDEMPOTENCY_MARKER = "<!-- AFFILIATE-CTA:"

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_html_files(directory: str) -> List[str]:
    """Return sorted list of .html files in directory (non-recursive)."""
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".html")
    ]
    return sorted(files)


def read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception as exc:
        return None


def write_file(path: str, content: str) -> bool:
    """
    Write an article through the validated atomic path. A refused write leaves the
    original file untouched and is reported by the caller as an error, which is the
    behaviour we want: injecting a CTA must never be the thing that truncates a page.
    """
    try:
        safe_write_html(path, content, allow_preexisting=True)
        return True
    except (IntegrityError, OSError) as exc:
        print("  WRITE REFUSED {}: {}".format(os.path.basename(path), exc))
        return False


def already_has_cta(content: str, affiliate_id: str) -> bool:
    return "<!-- AFFILIATE-CTA:{} -->".format(affiliate_id) in content


def content_matches_affiliate(content_lower: str, keywords: List[str]) -> bool:
    return any(kw in content_lower for kw in keywords)


def build_cta_block(affiliate: dict) -> str:
    return CTA_TEMPLATE.format(
        affiliate_id=affiliate["id"],
        affiliate_text=affiliate["cta_text"],
    )


def find_injection_point(content: str) -> Optional[int]:
    """
    Return the character index to insert the CTA block.
    Priority: before <footer, else before </body>.
    Returns None if neither found (skip the file).
    """
    idx = content.lower().find("<footer")
    if idx != -1:
        return idx
    idx = content.lower().find("</body>")
    if idx != -1:
        return idx
    return None


def inject_into_content(content: str, blocks: List[str]) -> str:
    """Insert all CTA blocks at the injection point, joined by newline."""
    idx = find_injection_point(content)
    if idx is None:
        return content
    combined = "\n".join(blocks) + "\n"
    return content[:idx] + combined + content[idx:]


def is_article_file(filename: str) -> bool:
    """Skip non-article pages."""
    skip = {
        "index.html", "about.html", "affiliate-disclosure.html",
        "contact.html", "privacy.html", "sitemap.html", "404.html",
    }
    return os.path.basename(filename) not in skip


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Inject affiliate CTA boxes into SEO articles.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)),
                        help="Directory to scan (default: script directory).")
    args = parser.parse_args()

    scan_dir = args.dir
    dry_run = args.dry_run

    print("=" * 60)
    print("ARIA Affiliate Link Injector")
    print("Directory : {}".format(scan_dir))
    print("Dry run   : {}".format(dry_run))
    print("=" * 60)

    html_files = get_html_files(scan_dir)
    print("HTML files found: {}\n".format(len(html_files)))

    # Counters per affiliate id
    counters = {aff["id"]: 0 for aff in AFFILIATES}
    skipped_already_injected = 0
    skipped_no_match = 0
    skipped_no_anchor = 0
    skipped_read_error = 0
    modified_files = []
    errors = []

    for path in html_files:
        if not is_article_file(path):
            continue

        content = read_file(path)
        if content is None:
            skipped_read_error += 1
            errors.append({"file": path, "reason": "read error"})
            continue

        content_lower = content.lower()

        # Determine which affiliates match this article
        blocks_to_inject = []
        matched_ids = []

        for aff in AFFILIATES:
            if already_has_cta(content, aff["id"]):
                continue  # idempotency: this affiliate already present
            if content_matches_affiliate(content_lower, aff["keywords"]):
                blocks_to_inject.append(build_cta_block(aff))
                matched_ids.append(aff["id"])

        if not blocks_to_inject:
            # Check if ALL were already injected vs no match at all
            all_already_present = all(
                already_has_cta(content, aff["id"]) for aff in AFFILIATES
                if content_matches_affiliate(content_lower, aff["keywords"])
            )
            if all_already_present and any(
                content_matches_affiliate(content_lower, aff["keywords"]) for aff in AFFILIATES
            ):
                skipped_already_injected += 1
            else:
                skipped_no_match += 1
            continue

        if find_injection_point(content) is None:
            skipped_no_anchor += 1
            errors.append({"file": path, "reason": "no injection anchor"})
            continue

        new_content = inject_into_content(content, blocks_to_inject)

        if dry_run:
            print("[DRY RUN] Would modify: {} (affiliates: {})".format(
                os.path.basename(path), ", ".join(matched_ids)))
        else:
            if write_file(path, new_content):
                for aid in matched_ids:
                    counters[aid] += 1
                modified_files.append({
                    "file": os.path.basename(path),
                    "affiliates": matched_ids,
                })
            else:
                errors.append({"file": path, "reason": "write error"})

        if not dry_run:
            pass
        else:
            for aid in matched_ids:
                counters[aid] += 1

    # ---------------------------------------------------------------------------
    # Report
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print("\nArticles modified per affiliate:\n")
    for aff in AFFILIATES:
        print("  {:20s}  {:>5d} articles".format(aff["name"], counters[aff["id"]]))

    total_modified = len(modified_files) if not dry_run else sum(counters.values())
    print("\nTotal articles touched     : {}".format(
        len(modified_files) if not dry_run else "(dry run - see counts above)"))
    print("Skipped (already injected) : {}".format(skipped_already_injected))
    print("Skipped (no keyword match) : {}".format(skipped_no_match))
    print("Skipped (no anchor tag)    : {}".format(skipped_no_anchor))
    print("Skipped (read error)       : {}".format(skipped_read_error))

    if errors:
        print("\nErrors ({}):\n".format(len(errors)))
        for e in errors[:20]:
            print("  [{}] {}".format(e["reason"], os.path.basename(e["file"])))
        if len(errors) > 20:
            print("  ... and {} more".format(len(errors) - 20))

    # Write JSON log
    if not dry_run:
        log = {
            "timestamp": datetime.now().isoformat(),
            "scan_dir": scan_dir,
            "counters": counters,
            "total_files_modified": len(modified_files),
            "skipped_already_injected": skipped_already_injected,
            "skipped_no_match": skipped_no_match,
            "skipped_no_anchor": skipped_no_anchor,
            "errors": errors,
            "modified_files": modified_files,
        }
        log_path = os.path.join(scan_dir, "affiliate_inject_log.json")
        try:
            safe_write_text(log_path, json.dumps(log, indent=2))
            print("\nLog saved to: {}".format(log_path))
        except Exception as exc:
            print("\nWARNING: could not write log: {}".format(exc))

    print("\nDone." + (" (DRY RUN — no files written)" if dry_run else ""))


if __name__ == "__main__":
    main()
