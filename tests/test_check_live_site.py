"""
Tests for check_live_site.py — the monitor that watches the deployment.

Everything here runs against a fake fetcher; no test touches the network. The point
is the same as for every other guard in this repo: prove the instrument answers the
question everyone reads it as answering. A monitor that goes green on a broken deploy
is worse than none, so the red cases matter more than the green one — several below
exist because an adversarial review found the original version passing them.
"""
import io
import re
import urllib.error
from pathlib import Path

import pytest

import check_live_site
from check_live_site import (
    google_ads_entries,
    looks_complete,
    make_fetcher,
    robots_block_for,
    rotating_indices,
    run_checks,
    sample_indices,
    sitemap_locs,
    smuggled_sitemaps,
)

BASE = "https://aria-capital.github.io/aria-seo-site/"
ROOT = "https://aria-capital.github.io/"
PUB = "pub-5576001602612111"
GA4 = "G-CDJDJDHBHN"
GOOD_ADS = f"google.com, {PUB}, DIRECT, f08c47fec0942fa0\n"
TAGS = (f'<script src="https://www.googletagmanager.com/gtag/js?id={GA4}"></script>'
        f'<script src="https://pagead2.googlesyndication.com/pagead/js/'
        f'adsbygoogle.js?client=ca-{PUB}"></script>')


def article(url):
    return (f'<html><head><link rel="canonical" href="{url}">{TAGS}</head>'
            f"<body>x</body></html>").encode()


def make_site():
    """A minimal healthy deployment as {url: (status, bytes)}, plus its committed
    files as {url: bytes} for the stale-deploy comparison."""
    locs = [BASE] + [f"{BASE}a{i}.html" for i in range(7)]
    sitemap = ("<urlset>" + "".join(f"<loc>{u}</loc>" for u in locs) + "</urlset>").encode()
    homepage = f"<html><head>{TAGS}</head><body>home</body></html>".encode()
    site = {
        BASE: (200, homepage),
        BASE + "sitemap.xml": (200, sitemap),
        BASE + "robots.txt": (200, f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n".encode()),
        ROOT + "robots.txt": (200, f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n".encode()),
        ROOT + "ads.txt": (200, GOOD_ADS.encode()),
        BASE + "ads.txt": (200, GOOD_ADS.encode()),
    }
    for u in locs[1:]:
        site[u] = (200, article(u))
    committed = {u: site[u][1] for u in locs}
    return site, sitemap, committed


def fetcher(site):
    def fetch(url):
        return site.get(url, (404, b"<html><body>404</body></html>"))
    return fetch


def run(site, local_sitemap=None, committed=None):
    results = run_checks(fetcher(site), BASE, PUB, GA4, local_sitemap,
                         local_bytes=(committed or {}).get, day_key=20260820)
    return {r["name"]: r for r in results}


# --- pure helpers --------------------------------------------------------------------

def test_scoped_disallow_elsewhere_is_not_a_block():
    assert robots_block_for("User-agent: *\nDisallow: /private/\n", "/aria-seo-site/") is None


def test_global_disallow_is_caught_despite_whitespace_case_and_no_space():
    assert robots_block_for("  disallow: /  \n", "/aria-seo-site/")
    assert robots_block_for("Disallow:/\n", "/aria-seo-site/")


def test_disallow_covering_the_project_prefix_is_a_block():
    assert robots_block_for("Disallow: /aria-\n", "/aria-seo-site/")
    assert robots_block_for("Disallow: /aria-seo-site/some-page.html\n", "/aria-seo-site/")
    assert robots_block_for("Disallow:\n", "/aria-seo-site/") is None  # empty = allow-all


def test_smuggled_sitemap_is_named_but_foreign_sitemaps_are_not_ours():
    text = (f"Sitemap: {BASE}sitemap.xml\nSitemap: {BASE}sitemap-all.xml\n"
            "Sitemap: https://elsewhere.example/sitemap.xml\n")
    assert smuggled_sitemaps(text, BASE) == [f"{BASE}sitemap-all.xml"]


def test_sitemap_locs_tolerates_whitespace():
    assert sitemap_locs("<loc>\n  https://x/a.html\n</loc>") == ["https://x/a.html"]


def test_sample_indices_deterministic_spread_and_bounds():
    assert sample_indices(939) == sample_indices(939)  # same articles every night
    idx = sample_indices(939)
    assert idx[0] == 0 and idx[-1] == 938 and len(idx) == 5
    assert sample_indices(2) == [0, 1]
    assert sample_indices(1) == [0]
    assert sample_indices(0) == []


def test_rotating_indices_deterministic_per_day_and_move_across_days():
    assert rotating_indices(939, 20260820) == rotating_indices(939, 20260820)
    assert rotating_indices(939, 20260820) != rotating_indices(939, 20260821)
    for day in (20260820, 20260821, 20270101):
        idx = rotating_indices(939, day)
        assert all(0 <= i < 939 for i in idx) and len(idx) == 5
    assert rotating_indices(0, 20260820) == []
    assert rotating_indices(3, 20260820)  # tiny corpus still works


def test_truncated_html_is_incomplete():
    assert looks_complete(b"<html><body>x</body></html>\n")
    assert not looks_complete(b"<html><body>x</bo")


def test_ads_entries_parse_fields_exactly():
    assert google_ads_entries(GOOD_ADS) == [(PUB, "DIRECT")]
    # a comment naming the pub is not authorization
    assert google_ads_entries(f"# google.com, {PUB}, DIRECT") == []
    # relationship and id come from their own fields, not substring luck
    assert google_ads_entries(f"google.com, {PUB}, RESELLER, x") == [(PUB, "RESELLER")]
    assert google_ads_entries(f"google.com, {PUB}9, DIRECT, x") == [(PUB + "9", "DIRECT")]


# --- the healthy deployment ----------------------------------------------------------

def test_healthy_site_passes_every_check():
    site, sitemap, committed = make_site()
    results = run(site, local_sitemap=sitemap, committed=committed)
    failing = [n for n, r in results.items() if not r["ok"]]
    assert failing == []


# --- red cases: each one is a real incident class this repo has already paid for -----

def test_truncated_article_fails_and_is_NAMED_not_counted():
    site, sitemap, committed = make_site()
    victim = BASE + "a3.html"
    site[victim] = (200, b"<html><body>cut off mid-")
    r = run(site, sitemap, committed)["sampled articles serve complete, committed, canonical, and tagged"]
    assert not r["ok"] and victim in r["detail"]


def test_stale_deploy_of_an_article_fails_even_though_page_is_wellformed():
    # The big adversarial finding: an OLD version of a page passes every status and
    # structure check. Only the byte comparison against the committed file sees it.
    site, sitemap, committed = make_site()
    victim = BASE + "a3.html"
    stale = article(victim).replace(b"<body>x</body>", b"<body>pre-repair content</body>")
    site[victim] = (200, stale)
    r = run(site, sitemap, committed)["sampled articles serve complete, committed, canonical, and tagged"]
    assert not r["ok"] and victim in r["detail"] and "stale" in r["detail"]


def test_stale_homepage_fails():
    site, sitemap, committed = make_site()
    site[BASE] = (200, f"<html><head>{TAGS}</head><body>old home</body></html>".encode())
    r = run(site, sitemap, committed)["homepage serves complete and matches the committed index.html"]
    assert not r["ok"] and "stale" in r["detail"] or "differ" in r["detail"]


def test_inert_tags_fail_the_functional_check():
    # The ids present in prose but the <script> loaders gone: presence testing passes
    # this; the functional check must not.
    site, sitemap, committed = make_site()
    site[BASE] = (200, f"<html><body>{GA4} {PUB}</body></html>".encode())
    committed = dict(committed)
    committed[BASE] = site[BASE][1]  # committed matches, so only the tag check fires
    r = run(site, sitemap, committed)["homepage carries a functional GA4 snippet + AdSense loader"]
    assert not r["ok"] and "missing" in r["detail"]


def test_live_sitemap_drift_from_committed_fails():
    site, sitemap, committed = make_site()
    r = run(site, local_sitemap=sitemap + b"<!-- newer commit -->", committed=committed)
    assert not r["live sitemap matches committed curation"]["ok"]


def test_no_local_sitemap_green_says_what_was_not_compared():
    site, sitemap, committed = make_site()
    r = run(site, local_sitemap=None, committed=committed)["live sitemap matches committed curation"]
    assert r["ok"] and "not compared" in r["detail"]


def test_foreign_host_in_sitemap_fails():
    site, sitemap, committed = make_site()
    bad = sitemap.replace(b"<loc>" + BASE.encode(),
                          b"<loc>https://carlostrujilloglz1991.github.io/", 1)
    site[BASE + "sitemap.xml"] = (200, bad)
    r = run(site)["live sitemap matches committed curation"]
    assert not r["ok"] and "carlostrujilloglz1991" in r["detail"]


def test_root_robots_blocking_the_project_fails():
    # Crawlers obey the HOST ROOT robots.txt, which lives in a repo with no CI.
    site, sitemap, committed = make_site()
    site[ROOT + "robots.txt"] = (200, b"User-agent: *\nDisallow: /aria-seo-site/\n")
    r = run(site, sitemap, committed)["ROOT robots.txt (separate repo!) does not block or redirect crawlers"]
    assert not r["ok"] and "blocks crawling" in r["detail"]


def test_root_robots_absent_is_allow_all():
    site, sitemap, committed = make_site()
    del site[ROOT + "robots.txt"]
    r = run(site, sitemap, committed)["ROOT robots.txt (separate repo!) does not block or redirect crawlers"]
    assert r["ok"]


def test_root_robots_smuggling_a_full_corpus_sitemap_fails():
    # The check_sitemap_curated.py hole, one host up: advertise sitemap-all.xml from
    # the root file and every repo-scoped guard stays green while crawlers ingest it.
    site, sitemap, committed = make_site()
    site[ROOT + "robots.txt"] = (200, (f"User-agent: *\nAllow: /\n"
                                       f"Sitemap: {BASE}sitemap.xml\n"
                                       f"Sitemap: {BASE}sitemap-all.xml\n").encode())
    r = run(site, sitemap, committed)["ROOT robots.txt (separate repo!) does not block or redirect crawlers"]
    assert not r["ok"] and "sitemap-all.xml" in r["detail"]


def test_rogue_second_publisher_in_root_ads_txt_fails():
    # Inventory laundering (standing priority 4): the expected line still present,
    # one more added. An 'is my line there' test can never see this.
    site, sitemap, committed = make_site()
    site[ROOT + "ads.txt"] = (200, (GOOD_ADS + "google.com, pub-9999999999999999, DIRECT, x\n").encode())
    r = run(site, sitemap, committed)["root ads.txt (separate repo!) authorizes exactly the expected publisher"]
    assert not r["ok"] and "pub-9999999999999999" in r["detail"]


def test_vanished_root_ads_txt_fails_loudly():
    site, sitemap, committed = make_site()
    del site[ROOT + "ads.txt"]
    assert not run(site, sitemap, committed)[
        "root ads.txt (separate repo!) authorizes exactly the expected publisher"]["ok"]


def test_empty_article_set_is_not_a_vacuous_green():
    site, sitemap, committed = make_site()
    homepage_only = f"<urlset><loc>{BASE}</loc></urlset>".encode()
    site[BASE + "sitemap.xml"] = (200, homepage_only)
    r = run(site, local_sitemap=homepage_only, committed=committed)[
        "sampled articles serve complete, committed, canonical, and tagged"]
    assert not r["ok"] and "no articles" in r["detail"]


def test_soft_200_on_unknown_path_fails():
    site, sitemap, committed = make_site()
    orig = fetcher(site)

    def soft(url):
        status, body = orig(url)
        return (200, body) if status == 404 else (status, body)

    results = {r["name"]: r for r in run_checks(soft, BASE, PUB, GA4, sitemap,
                                                local_bytes=committed.get, day_key=1)}
    assert not results["unknown paths return a real 404"]["ok"]


def test_one_crashing_check_does_not_silence_the_others():
    def explode(url):
        raise OSError("network down")

    results = run_checks(explode, BASE, PUB, GA4, None)
    assert len(results) == 9  # every check reported
    assert all(not r["ok"] for r in results)


def test_run_checks_never_writes(tmp_path, monkeypatch):
    """Read-only is a stated property, so pin it: a run must not create or modify
    files even when everything fails."""
    monkeypatch.chdir(tmp_path)
    run_checks(fetcher({}), BASE, PUB, GA4, None)
    assert list(tmp_path.iterdir()) == []


# --- the fetcher's retry contract ----------------------------------------------------

def _urlopen_sequence(monkeypatch, outcomes):
    """Feed make_fetcher a scripted urlopen; sleep is a no-op so tests stay fast."""
    calls = []

    def fake_urlopen(req, timeout=None, context=None):
        outcome = outcomes[min(len(calls), len(outcomes) - 1)]
        calls.append(req.full_url)
        if isinstance(outcome, Exception):
            raise outcome

        class R:
            status = outcome[0]
            def read(self):
                return outcome[1]
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return R()

    monkeypatch.setattr(check_live_site.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(check_live_site.time, "sleep", lambda s: None)
    return calls


def http_error(code):
    return urllib.error.HTTPError("u", code, "err", None, io.BytesIO(b"err"))


def test_transient_503_is_retried_to_success(monkeypatch):
    # The adversarial finding: HTTPError used to short-circuit the retry loop, so a
    # single CDN blip turned into a red night.
    calls = _urlopen_sequence(monkeypatch, [http_error(503), (200, b"fine")])
    status, body = make_fetcher()("https://x/")
    assert (status, body) == (200, b"fine") and len(calls) == 2


def test_404_is_an_answer_never_retried(monkeypatch):
    calls = _urlopen_sequence(monkeypatch, [http_error(404)])
    status, _ = make_fetcher()("https://x/")
    assert status == 404 and len(calls) == 1


def test_persistent_503_still_fails_after_all_attempts(monkeypatch):
    calls = _urlopen_sequence(monkeypatch, [http_error(503)])
    status, _ = make_fetcher()("https://x/")
    assert status == 503 and len(calls) == len(check_live_site.RETRY_GAPS) + 1


# --- repo-side mirror: pin the corpus to the monitor's own predicates ----------------

def test_every_advertised_committed_article_satisfies_the_monitors_predicates():
    """If a future writer changes canonical formatting, drops a tag, or lands a
    truncated file in the advertised set, fail HERE at PR time — not as a confusing
    red from the 3am monitor naming an innocent-looking page. This also makes the
    nightly sample rotation safe: the whole curated set is pre-validated."""
    repo = Path(check_live_site.REPO)
    sitemap = repo / "sitemap.xml"
    if not sitemap.is_file():
        pytest.skip("no sitemap.xml in tree")
    base = check_live_site.FALLBACK_BASE
    pub, ga4 = check_live_site.FALLBACK_PUB, check_live_site.FALLBACK_GA4
    offenders = []
    for url in sitemap_locs(sitemap.read_text()):
        if url.rstrip("/") == base.rstrip("/"):
            continue
        f = repo / url[len(base):]
        raw = f.read_bytes()
        text = raw.decode("utf-8", "replace")
        if not looks_complete(raw):
            offenders.append(f"{f.name}: incomplete")
        elif f'<link rel="canonical" href="{url}">' not in text:
            offenders.append(f"{f.name}: canonical shape drifted")
        elif (f"googletagmanager.com/gtag/js?id={ga4}" not in text
              or f"adsbygoogle.js?client=ca-{pub}" not in text):
            offenders.append(f"{f.name}: revenue tags missing")
    assert offenders == [], offenders[:10]
