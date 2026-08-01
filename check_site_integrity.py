#!/usr/bin/env python3
"""
check_site_integrity.py — write-time guard against the recurring truncation bug.

WHY THIS EXISTS
The truncation-bug family has silently cut off index.html, sitemap.xml, the
Session Brief, trade_journal.py, and president.py mid-write — each one only
caught a session or more later, after a HIGH-severity manual repair. This guard
catches the same damage AT WRITE TIME so a writer can refuse to ship a corrupt
file instead of leaving it broken for the next session to find.

WHAT IT CHECKS (index.html + sitemap.xml, the two files that keep breaking)
  index.html
    - non-empty
    - rstrip() ends with </html>            (the classic truncation signature)
    - exactly one </head>, </body>, </html>, </footer>
    - <div> / </div> balanced               (cut-off-mid-card signature)
    - every  href="X.html"  resolves to a real local file (no broken cards)
  sitemap.xml
    - parses as valid XML
    - every <loc> maps to a real local .html file

USAGE
  CLI (exit 0 = clean, exit 1 = problems found):
      python check_site_integrity.py
  Writers (call right after writing index.html / sitemap.xml):
      from check_site_integrity import assert_site_integrity
      assert_site_integrity()        # raises IntegrityError on any failure
  Generic single-file guard for any full HTML doc you just wrote:
      from check_site_integrity import check_html_closed
      check_html_closed("some-article.html")   # returns list of problems
"""
from __future__ import annotations
import os
import re
import sys
import xml.dom.minidom as minidom

# Resolve paths relative to THIS file so it works from any cwd.
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(SITE_DIR, "index.html")
SITEMAP = os.path.join(SITE_DIR, "sitemap.xml")


class IntegrityError(Exception):
    """Raised by assert_site_integrity() when any check fails."""


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_html_closed(path: str) -> list[str]:
    """Generic guard for a single full HTML document. Returns problems (empty = OK)."""
    problems: list[str] = []
    if not os.path.exists(path):
        return [f"{os.path.basename(path)}: file does not exist"]
    html = _read(path)
    name = os.path.basename(path)
    if not html.strip():
        return [f"{name}: file is empty"]
    if not html.rstrip().endswith("</html>"):
        problems.append(f"{name}: does NOT end with </html> (truncated mid-write?)")
    open_div = len(re.findall(r"<div\b", html))
    close_div = html.count("</div>")
    if open_div != close_div:
        problems.append(f"{name}: <div> imbalance — {open_div} open vs {close_div} close")
    for tag in ("</head>", "</body>", "</html>"):
        n = html.count(tag)
        if n != 1:
            problems.append(f"{name}: expected exactly 1 '{tag}', found {n}")
    return problems


def html_severity(html: str) -> dict:
    """
    Structured, *comparable* corruption metrics for an HTML document.

    check_html_closed() answers "is this file corrupt?" — a yes/no that is useless
    on a corpus where two thirds of the files are already corrupt. This answers
    "how corrupt?", so a caller can allow a write that leaves a file no worse than
    it found it while still refusing one that makes it worse. Lower is better;
    every value is a non-negative int/bool so metrics compare field by field.

    `block_delta` and `misnested` cover every container tag, not just <div>. They were
    added after a truncated <footer> in dmca-policy.html and another in
    nurse-real-estate-investing.html scored as perfectly clean here: only <div> was being
    counted, so an unclosed <footer>, <main>, <article>, <ol> or <table> was invisible to
    both gates. Fourteen more files were carrying the same damage.
    """
    return {
        "unterminated": not html.rstrip().endswith("</html>"),
        "div_delta": abs(len(re.findall(r"<div\b", html)) - html.count("</div>")),
        "tag_errors": sum(abs(html.count(t) - 1) for t in ("</head>", "</body>", "</html>")),
        "unterminated_attr": len(re.findall(r'<[a-zA-Z][^>]*?\s[a-zA-Z-]+="[^"\n]*$', html, re.M)),
        "block_delta": sum(
            abs(len(re.findall(r"<%s\b" % t, html)) - html.count("</%s>" % t))
            for t in CONTAINER_TAGS
            if t != "div"
        ),
        "misnested": _misnested(html),
    }


# Elements that must nest. <p>, <li> and <td> are deliberately absent: the corpus closes
# them loosely — a stray </p> with no <p> is the house style inside every callout — so
# counting them would report damage that is not there.
CONTAINER_TAGS = (
    "div", "main", "article", "section", "aside", "nav", "header", "footer",
    "ol", "ul", "table", "form", "figure", "blockquote",
)
_NESTING_TOKEN = re.compile(r"</?(%s)\b[^>]*>" % "|".join(CONTAINER_TAGS))


def _misnested(html: str) -> bool:
    """True if some closing tag does not close the innermost element that is open."""
    stack: list[str] = []
    for m in _NESTING_TOKEN.finditer(html):
        token, name = m.group(0), m.group(1)
        if token.startswith("</"):
            if not stack or stack[-1] != name:
                return True
            stack.pop()
        elif not token.endswith("/>"):
            stack.append(name)
    return bool(stack)


def severity_regressions(before: dict, after: dict) -> list[str]:
    """Return a message per metric that got WORSE going from `before` to `after`."""
    out: list[str] = []
    for key in sorted(set(before) | set(after)):
        b, a = int(before.get(key, 0)), int(after.get(key, 0))
        if a > b:
            out.append(f"{key}: {b} -> {a}")
    return out


def check_index(path: str = INDEX) -> list[str]:
    """index.html-specific checks, including no-broken-card-links."""
    problems = check_html_closed(path)
    if any("does not exist" in p or "is empty" in p for p in problems):
        return problems
    html = _read(path)
    name = os.path.basename(path)
    if html.count("</footer>") != 1:
        problems.append(f"{name}: expected exactly 1 '</footer>', found {html.count('</footer>')}")
    # Every internal .html link must resolve to a real local file.
    for href in re.findall(r'href="([^"]+\.html)"', html):
        if href.startswith(("http://", "https://", "//")) or "#" in href:
            continue
        target = os.path.join(SITE_DIR, href)
        if not os.path.exists(target):
            problems.append(f"{name}: broken card link -> {href} (no such file)")
    return problems


def check_sitemap(path: str = SITEMAP) -> list[str]:
    """sitemap.xml: valid XML + every <loc> maps to a real local .html file."""
    problems: list[str] = []
    name = os.path.basename(path)
    if not os.path.exists(path):
        return [f"{name}: file does not exist"]
    xml = _read(path)
    try:
        minidom.parseString(xml)
    except Exception as exc:  # noqa: BLE001 — surface any parse failure
        return [f"{name}: invalid XML — {exc}"]
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
    if not locs:
        problems.append(f"{name}: no <loc> entries found")
    for loc in locs:
        slug = loc.rstrip("/").split("/")[-1]
        if not slug.endswith(".html"):
            continue  # directory/root URL, nothing local to map
        if not os.path.exists(os.path.join(SITE_DIR, slug)):
            problems.append(f"{name}: <loc> points to missing file -> {slug}")
    return problems


def run_all() -> list[str]:
    return check_index() + check_sitemap()


def assert_site_integrity() -> None:
    """For writers: raise IntegrityError if index.html or sitemap.xml is corrupt."""
    problems = run_all()
    if problems:
        raise IntegrityError("Site integrity check FAILED:\n  - " + "\n  - ".join(problems))


def main() -> int:
    problems = run_all()
    if problems:
        print("FAIL — site integrity problems found:")
        for p in problems:
            print("  -", p)
        return 1
    n_cards = len(set(re.findall(r'href="([^"]+\.html)"', _read(INDEX))))
    n_locs = len(re.findall(r"<loc>", _read(SITEMAP)))
    print(f"PASS — index.html closed & div-balanced, {n_cards} unique card links all resolve; "
          f"sitemap.xml valid XML, {n_locs} locs all map to real files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
