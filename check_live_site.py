#!/usr/bin/env python3
"""
check_live_site.py — measure the DEPLOYED site, which no repo-side gate can see.

WHY THIS EXISTS
Every gate in this repo reads the working tree. The thing that earns (or fails to earn)
money is the GitHub Pages deployment — a different artifact, published asynchronously,
which can drift from the repo with every repo-side check still green: a Pages build can
fail silently and leave a stale site up; a truncated deploy would resurrect the exact
class of damage `safe_write.py` exists to prevent, one layer beyond its reach; and the
files Google actually reads for authorization and crawl policy — ads.txt AND robots.txt —
live at the HOST ROOT in the separate `aria-capital.github.io` repo, where nothing in
this repo's CI can even look. (Added 2026-08-19, alongside the nightly live-site
Routine; hardened the same day by an adversarial review that found the original version
never fetched the root robots.txt, could not see a rogue second publisher line, and
treated any HTTP 5xx as final instead of retrying.)

WHAT IT ASSERTS, PRECISELY
Only what can be measured over anonymous HTTPS:
  - the homepage serves complete and byte-identical to the committed index.html;
  - the homepage carries a FUNCTIONAL GA4 snippet and AdSense loader (the script URLs,
    not just the ids appearing somewhere in the text);
  - the live sitemap is byte-identical to the committed curated one (drift detection —
    a red here minutes after a merge usually just means the Pages deploy is in flight);
  - BOTH robots.txt files — the host root one crawlers actually obey, and the project
    one — neither block the site nor point crawlers at any sitemap under this site
    other than the curated one;
  - root and project ads.txt authorize EXACTLY the expected publisher: one google.com
    line, DIRECT, that pub id and no other (an extra line is the inventory-laundering
    pattern standing priority 4 warns about, and this is the only guard that reads the
    root file);
  - a sample of advertised articles — five fixed plus five rotating by date, so every
    article is eventually visited while a red still names the same file all day —
    serves complete, byte-identical to its committed file, with its own canonical and
    both revenue tags;
  - unknown paths return a real 404 (a soft-200 would poison the index).

WHAT IT DOES NOT ASSERT
Whether Google has indexed anything, whether any page gets traffic, or whether any
monetization account is approved. Those live behind Search Console / GA4 / AdSense
logins this script does not have. A green run here means "the machine is serving what
the repo intends" — it says nothing about whether anyone is looking at it.

This is read-only: it writes nothing, locally or remotely. Exit 0 = all checks pass,
1 = at least one failed. `--json` prints machine-readable results, including the repo
HEAD the expectations were derived from, so a report is auditable against staleness.

USAGE
    python3 check_live_site.py           # human-readable table
    python3 check_live_site.py --json    # for the nightly Routine
"""

from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Fallbacks for a standalone run (e.g. the owner's Mac, outside the repo). When the repo
# is present the same values are derived from it instead, so the live site is compared
# against what the tree actually says rather than against a constant that can go stale.
FALLBACK_BASE = "https://aria-capital.github.io/aria-seo-site/"
FALLBACK_PUB = "pub-5576001602612111"
FALLBACK_GA4 = "G-CDJDJDHBHN"

TIMEOUT = 30
RETRY_GAPS = (4, 30)  # seconds between attempts; a 4s window is thin for an edge blip
RETRYABLE = {429, 500, 502, 503, 504}
# Deliberately gibberish so it can never collide with a real article slug.
MISSING_PATH = "this-page-must-not-exist-9f2c1b.html"


def base_url() -> str:
    """The canonical host, from the repo's own reader when available."""
    try:
        sys.path.insert(0, str(REPO))
        from generate_sitemap import read_base_url  # read-only; refuses dead hosts
        return read_base_url()
    except Exception:
        return FALLBACK_BASE
    finally:
        sys.path.remove(str(REPO))


def expected_pub() -> str:
    try:
        m = re.search(r"pub-\d{6,}", (REPO / "ads.txt").read_text())
        if m:
            return m.group(0)
    except OSError:
        pass
    return FALLBACK_PUB


def expected_ga4() -> str:
    """Anchored to the gtag snippet, not the first G-… string anywhere in the file —
    a product code in a card title must not silently become the 'expected' id."""
    try:
        text = (REPO / "index.html").read_text()
        m = (re.search(r"googletagmanager\.com/gtag/js\?id=(G-[A-Z0-9]{6,})", text)
             or re.search(r"G-[A-Z0-9]{6,}", text))
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    except OSError:
        pass
    return FALLBACK_GA4


def repo_head() -> str:
    """Which checkout the expectations came from — so two greens are distinguishable."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cI"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def make_fetcher():
    """Real HTTPS fetcher: returns (status_code, bytes). Honors proxy env vars; trusts
    the agent-proxy CA bundle when running in a cloud container. Transient failures —
    including HTTP 429/5xx, which GitHub Pages' CDN does emit during incidents — are
    retried, because a nightly monitor that flaps on a transient is a monitor people
    learn to ignore. A 404 is an answer, never retried."""
    ctx = ssl.create_default_context()  # already honors SSL_CERT_FILE
    for cand in (os.environ.get("CURL_CA_BUNDLE"), os.environ.get("REQUESTS_CA_BUNDLE"),
                 "/root/.ccr/ca-bundle.crt"):
        if not cand:
            continue
        try:
            if Path(cand).is_file():
                ctx.load_verify_locations(cand)
        except (OSError, ssl.SSLError):
            # Unreadable (is_file raises EACCES for a non-root user probing /root —
            # it only swallows not-found) or invalid: either way the bundle is not
            # usable here and the default trust store still applies.
            pass

    # A redirect is an answer, not a detour (review 2026-09-02). urlopen follows redirects
    # silently, so a site that had moved hosts — every URL a 301 to somewhere else — read as
    # byte-identical and fully green. The response's final URL is compared to the one asked
    # for; if they differ the status comes back as "redirected to <final>", which fails the
    # check that saw it with the honest reason: the deployment is not where the repo says.
    def fetch(url: str):
        last = None
        for attempt in range(len(RETRY_GAPS) + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "aria-live-check/1"})
                with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                    final = getattr(r, "url", None) or url
                    if final != url:
                        return f"redirected to {final}", r.read()
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE and attempt < len(RETRY_GAPS):
                    last = e
                else:
                    return e.code, e.read()
            except Exception as e:  # DNS, TLS, timeout
                last = e
            if attempt < len(RETRY_GAPS):
                time.sleep(RETRY_GAPS[attempt])
        raise last

    return fetch


# --- pure helpers, unit-tested without network ---------------------------------------

def robots_block_for(robots_text: str, project_path: str) -> str | None:
    """The Disallow rule that would stop Google reaching the project, or None.

    Only the groups Google obeys count: `User-agent: *` and `User-agent: Googlebot`. A
    block aimed at GPTBot or CCBot is a legitimate edit and is ignored (rules before any
    User-agent line apply to everyone). '/', '/*' and '*' are the whole host; a prefix of
    the project path is a block; a rule INSIDE the project ('/aria-seo-site/feed') is a
    scoped rule, not a block — reviewed 2026-09-02, it used to page the owner nightly.
    Whitespace collapses first: 'Disallow:/' with no space is equally valid."""
    applies = True      # until the first User-agent line, rules apply to everyone
    in_header = False   # consecutive User-agent lines form one group header
    for line in robots_text.splitlines():
        flat = "".join(line.split())
        low = flat.lower()
        if low.startswith("user-agent:"):
            agent = low[len("user-agent:"):]
            mine = agent in ("*", "googlebot")
            applies = (applies or mine) if in_header else mine
            in_header = True
            continue
        if not low.startswith("disallow:"):
            if flat:
                in_header = False
            continue
        in_header = False
        rule = flat[len("disallow:"):]
        if not rule:
            continue  # empty Disallow means allow-all
        if not applies:
            continue
        if rule in ("/", "/*", "*") or project_path.startswith(rule.rstrip("*")):
            return line.strip()
    return None


def sitemap_lines(robots_text: str) -> list[str]:
    return [l.split(":", 1)[1].strip() for l in robots_text.splitlines()
            if l.lower().startswith("sitemap:")]


def smuggled_sitemaps(robots_text: str, base: str) -> list[str]:
    """Sitemap directives that point crawlers at anything under this site OTHER than
    the curated sitemap. This is the hole check_sitemap_curated.py documents: a second
    sitemap advertised from robots.txt ingests the full corpus while every file-scoped
    check stays green. Foreign-site sitemaps (the root repo's own, one day) are not
    ours to police."""
    return [s for s in sitemap_lines(robots_text)
            if s.startswith(base) and s != base + "sitemap.xml"]


def sitemap_locs(xml_text: str) -> list[str]:
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", xml_text)


def google_ads_entries(ads_text: str) -> list[tuple[str, str]]:
    """Every google.com authorization in an ads.txt, as (publisher id, relationship).
    Exact field parsing — a substring test passes a mistyped superstring id, and a
    mere 'is my line present' test can never see a rogue EXTRA line."""
    entries = []
    for line in ads_text.splitlines():
        line = line.split("#", 1)[0].strip()
        fields = [f.strip() for f in line.split(",")]
        if len(fields) >= 3 and fields[0].lower() == "google.com":
            entries.append((fields[1], fields[2].upper()))
    return entries


def sample_indices(n: int, k: int = 5) -> list[int]:
    """Deterministic spread across the sitemap — the same articles every night, so a
    red names the same file twice running instead of a different one each time."""
    if n <= 0:
        return []
    return sorted({min(n - 1, i * (n - 1) // (k - 1)) for i in range(k)}) if k > 1 else [0]


def rotating_indices(n: int, day_key: int, k: int = 5) -> list[int]:
    """Five more, advancing with the date, so the other ~930 articles are not a
    permanent blind spot: the fixed sample alone converts 'sample' into an allowlist.
    Pure function of (n, day) — deterministic within a day, walks the corpus across
    days."""
    if n <= 0:
        return []
    step = max(1, n // k)
    return sorted({(day_key + j * step) % n for j in range(k)})


def looks_complete(html_bytes: bytes) -> bool:
    """The deploy-layer version of the truncation check: a cut-off upload loses the
    tail first."""
    return html_bytes.rstrip().endswith(b"</html>")


# --- the checks ----------------------------------------------------------------------

def run_checks(fetch, base: str, pub: str, ga4: str, local_sitemap: bytes | None,
               local_bytes=None, day_key: int = 0):
    """Every check is (name, ok, detail). One check blowing up must not silence the
    rest — the whole point is a complete picture of the deployment each night.

    `local_bytes(url) -> bytes | None` maps a live URL to its committed file, enabling
    stale-deploy detection: without it, a Pages build stuck on an old commit serves
    pre-repair content forever with every status/structure check green (the sitemap
    byte-compare only catches the minority of pushes that touch sitemap.xml)."""
    results = []

    def check(name):
        def wrap(fn):
            try:
                ok, detail = fn()
            except Exception as e:
                ok, detail = False, f"check crashed: {type(e).__name__}: {e}"
            results.append({"name": name, "ok": bool(ok), "detail": detail})
        return wrap

    parts = base.split("/", 3)  # https:, '', host, project-path/
    root = f"{parts[0]}//{parts[2]}/"
    project_path = "/" + parts[3] if len(parts) > 3 else "/"

    gtag_needle = f"googletagmanager.com/gtag/js?id={ga4}"
    loader_needle = f"adsbygoogle.js?client=ca-{pub}"

    @check("homepage serves complete and matches the committed index.html")
    def _():
        status, body = fetch(base)
        if status != 200:
            return False, f"HTTP {status}"
        if not looks_complete(body):
            return False, "response does not end with </html> — truncated deploy?"
        committed = local_bytes(base) if local_bytes else None
        if committed is not None and body != committed:
            return False, ("bytes differ from committed index.html — deploy stale "
                           "or in flight")
        return True, f"{len(body)} bytes" + ("" if committed is not None
                                             else " (no local copy — drift not compared)")

    @check("homepage carries a functional GA4 snippet + AdSense loader")
    def _():
        # Asserts the script URLs, not bare ids: an id surviving in prose while the
        # <script> tag is gone would pass a presence test with analytics silently dead.
        # No entity-name assertion here: the committed homepage says "ICU Notebook",
        # not "ARIA Capital" (the three-brands question in CLAUDE.md, owner's call) —
        # this monitor checks that the deploy matches the repo, not that the repo is wise.
        _, body = fetch(base)
        text = body.decode("utf-8", "replace")
        missing = [label for label, needle in
                   ((f"gtag loader for {ga4}", gtag_needle),
                    (f"AdSense loader for {pub}", loader_needle))
                   if needle not in text]
        return (False, "missing: " + ", ".join(missing)) if missing else \
               (True, f"{ga4} and {pub} loaders present")

    @check("live sitemap matches committed curation")
    def _():
        status, body = fetch(base + "sitemap.xml")
        if status != 200:
            return False, f"HTTP {status}"
        locs = sitemap_locs(body.decode("utf-8", "replace"))
        if not locs:
            return False, "live sitemap has zero <loc> entries"
        stray = [u for u in locs if not u.startswith(base)]
        if stray:
            return False, f"foreign host advertised, e.g. {stray[0]}"
        if local_sitemap is None:
            return True, f"{len(locs)} locs (no local sitemap.xml — drift not compared)"
        if body != local_sitemap:
            age = _commit_age("sitemap.xml")
            return False, (f"{len(locs)} live locs but bytes differ from committed "
                           f"sitemap.xml{age} — drift, or a Pages deploy in flight")
        return True, f"{len(locs)} locs, byte-identical to the repo"

    @check("ROOT robots.txt (separate repo!) does not block or redirect crawlers")
    def _():
        # Crawlers only obey the robots.txt at the root of the HOST (RFC 9309) — the
        # project-path copy below is advisory at best. The root file lives in the
        # aria-capital.github.io repo, which has no CI: this is its only guard, the
        # same situation as ads.txt. A 404 is fine (no robots = allow-all).
        status, body = fetch(root + "robots.txt")
        if status == 404:
            return True, "absent — crawlers default to allow-all"
        if status != 200:
            return False, f"HTTP {status} at {root}robots.txt"
        text = body.decode("utf-8", "replace")
        rule = robots_block_for(text, project_path)
        if rule:
            return False, f"'{rule}' at the host root blocks crawling of this site"
        rogue = smuggled_sitemaps(text, base)
        if rogue:
            return False, f"root robots.txt advertises a non-curated sitemap: {rogue[0]}"
        return True, "present, no blocking rules, no non-curated sitemap advertised"

    @check("project robots.txt points at the curated sitemap only")
    def _():
        status, body = fetch(base + "robots.txt")
        if status != 200:
            return False, f"HTTP {status}"
        text = body.decode("utf-8", "replace")
        rule = robots_block_for(text, project_path)
        if rule:
            return False, f"'{rule}' is live"
        maps = sitemap_lines(text)
        if maps != [base + "sitemap.xml"]:
            return False, f"Sitemap lines are {maps or 'absent'}"
        return True, "allow-all, single curated Sitemap line"

    @check("root ads.txt (separate repo!) authorizes exactly the expected publisher")
    def _():
        status, body = fetch(root + "ads.txt")
        if status != 200:
            return False, f"HTTP {status} at {root}ads.txt — AdSense reads THIS file"
        entries = google_ads_entries(body.decode("utf-8", "replace"))
        if entries != [(pub, "DIRECT")]:
            return False, (f"google.com entries are {entries}, expected exactly "
                           f"[('{pub}', 'DIRECT')] — an extra or foreign id is the "
                           "inventory-laundering pattern")
        return True, f"exactly one entry: google.com/{pub}/DIRECT"

    @check("project ads.txt agrees")
    def _():
        status, body = fetch(base + "ads.txt")
        if status != 200:
            return False, f"HTTP {status}"
        entries = google_ads_entries(body.decode("utf-8", "replace"))
        ok = entries == [(pub, "DIRECT")]
        return ok, (f"exactly one entry: google.com/{pub}/DIRECT" if ok
                    else f"google.com entries are {entries}")

    @check("sampled articles serve complete, committed, canonical, and tagged")
    def _():
        _, body = fetch(base + "sitemap.xml")
        locs = sorted(u for u in sitemap_locs(body.decode("utf-8", "replace"))
                      if u.rstrip("/") != base.rstrip("/"))
        if not locs:
            return False, "sitemap advertises no articles — nothing to sample"
        picked = sorted(set(sample_indices(len(locs)) +
                            rotating_indices(len(locs), day_key)))
        bad = []
        for i in picked:
            url = locs[i]
            status, page = fetch(url)
            text = page.decode("utf-8", "replace")
            committed = local_bytes(url) if local_bytes else None
            if status != 200:
                bad.append(f"{url} -> HTTP {status}")
            elif not looks_complete(page):
                bad.append(f"{url} -> truncated")
            elif committed is not None and page != committed:
                bad.append(f"{url} -> differs from committed file (stale deploy?)")
            elif f'<link rel="canonical" href="{url}">' not in text:
                bad.append(f"{url} -> canonical missing or foreign")
            elif gtag_needle not in text or loader_needle not in text:
                bad.append(f"{url} -> revenue tags missing")
        if bad:
            return False, "; ".join(bad)  # names, not a count — a count is not actionable
        return True, f"{len(picked)} of {len(locs)} sampled (5 fixed + rotating), all clean"

    @check("unknown paths return a real 404")
    def _():
        status, _body = fetch(base + MISSING_PATH)
        return (status == 404,
                f"HTTP {status}" + ("" if status == 404 else " — soft-404s poison the index"))

    return results


def _commit_age(relpath: str) -> str:
    """', committed Nh ago' for the drift detail — lets the reader tell a deploy in
    flight (minutes old) from real drift, using commit time. NOT file mtime: a fresh
    clone stamps every file with clone time, which would mark all drift as fresh."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%ct",
                              "--", relpath], capture_output=True, text=True, timeout=10)
        age = int(time.time()) - int(out.stdout.strip())
        return f" (committed {age // 3600}h{age % 3600 // 60:02d}m ago)"
    except Exception:
        return ""


def main(argv: list[str]) -> int:
    base = base_url()

    def local_bytes(url: str):
        rel = "index.html" if url.rstrip("/") == base.rstrip("/") else url[len(base):]
        p = REPO / rel
        return p.read_bytes() if url.startswith(base) and p.is_file() else None

    local = REPO / "sitemap.xml"
    results = run_checks(make_fetcher(), base, expected_pub(), expected_ga4(),
                         local.read_bytes() if local.is_file() else None,
                         local_bytes=local_bytes,
                         day_key=int(time.strftime("%Y%m%d")))
    ok = all(r["ok"] for r in results)
    head = repo_head()
    if "--json" in argv:
        print(json.dumps({"base": base, "repo_head": head, "ok": ok,
                          "checks": results}, indent=2))
    else:
        print(f"live site: {base}   (expectations from repo @ {head})")
        for r in results:
            mark = "ok  " if r["ok"] else "FAIL"
            print(f"  {mark} {r['name']:<58} {r['detail']}")
        print("all checks passed" if ok else "AT LEAST ONE CHECK FAILED", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
