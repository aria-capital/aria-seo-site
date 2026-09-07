"""
Tests for the Jekyll exclude list in _config.yml.

WHY THIS EXISTS

On 2026-09-02 a session added `- feed` to the exclude list to stop two dead RSS feeds
being served. GitHub Pages builds with Jekyll 3.10, whose exclude filter matches by
**string prefix** as well as by glob — so that entry would also have dropped
`feeding-intolerance-gastric-residuals-icu-nurses-2026.html`, a live article advertised
in the sitemap. A reviewer caught it before it shipped.

The fix that landed was a comment. That is this repo's defining failure in miniature:
`safe_write.py` was a guard nothing called, and a warning nothing executes is the same
shape. The rule needs to be a check, so here it is.

The session that wrote the bug had "verified" the change — by confirming that exclusion
works at all (CLAUDE.md 404s, ads.txt still 200s). That answered a narrower question than
the one it was read as. These tests answer the actual one: does any entry drop something
it should not?
"""
import os

import pytest
import yaml

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(HERE, "_config.yml")

GLOB_CHARS = set("*?[]")


@pytest.fixture(scope="module")
def excludes():
    with open(CONFIG, encoding="utf-8") as fh:
        return [str(e) for e in (yaml.safe_load(fh).get("exclude") or [])]


@pytest.fixture(scope="module")
def repo_paths():
    return sorted(p for p in os.listdir(HERE) if not p.startswith("."))


def _literal(excludes):
    """Entries with no glob metacharacter — the ones Jekyll prefix-matches."""
    return [e for e in excludes if not (set(e) & GLOB_CHARS)]


# --- the prefix trap --------------------------------------------------------


def test_no_literal_exclude_prefix_matches_an_html_page(excludes, repo_paths):
    """
    The bug, pinned. `feed` looks like it names one file; Jekyll reads it as a prefix and
    silently takes every path that starts with those four characters — including a live
    article. Nothing else in this repo would have noticed: the build succeeds, CI is green,
    and the page simply stops existing.

    A file that must stop being served goes under an underscore directory instead, which
    Jekyll skips by default and which cannot collide with an article name.
    """
    casualties = {}
    for entry in _literal(excludes):
        hit = [p for p in repo_paths if p.startswith(entry) and p.endswith(".html")]
        if hit:
            casualties[entry] = hit
    assert not casualties, (
        "these exclude entries would drop published pages by prefix match: "
        f"{casualties} — move the target under an underscore directory instead"
    )


def test_no_literal_exclude_silently_takes_extra_paths(excludes, repo_paths):
    """
    Wider than the rule above: an entry should match the thing it names and nothing else.
    Matching a second path is how the article loss happened, and the next collision may
    not be a .html file.
    """
    greedy = {
        entry: sorted(p for p in repo_paths if p.startswith(entry) and p != entry)
        for entry in _literal(excludes)
    }
    greedy = {k: v for k, v in greedy.items() if v}
    assert not greedy, f"exclude entries matching more than they name: {greedy}"


# --- the things that must keep serving --------------------------------------


def test_no_txt_glob_is_ever_added(excludes):
    """
    ads.txt authorizes the AdSense publisher and robots.txt lets crawlers in. A `*.txt`
    glob would silently take both, and the symptom would be an unexplained monetization
    failure weeks later. The existing comment in _config.yml says this; now it is checked.
    """
    for entry in excludes:
        assert not entry.strip().endswith("*.txt"), f"a .txt glob would kill ads.txt: {entry!r}"


@pytest.mark.parametrize("must_serve", ["ads.txt", "robots.txt", "sitemap.xml", "index.html"])
def test_load_bearing_files_are_not_excluded(excludes, must_serve):
    for entry in excludes:
        if set(entry) & GLOB_CHARS:
            continue
        assert not must_serve.startswith(entry), f"{must_serve} would be dropped by {entry!r}"


def test_nojekyll_is_absent(repo_paths):
    """
    A .nojekyll file turns the whole build off, and underscore-prefixed exclusions —
    including _unpublished_feeds/ — stop working the moment it exists.
    """
    assert ".nojekyll" not in os.listdir(HERE)


# --- what actually stopped serving ------------------------------------------


def test_the_dead_feeds_live_under_an_underscore_directory():
    """
    The two 'Midnight Brief' feeds advertised 34 /newsletter/ URLs that all 404. They are
    withheld from the build by living under an underscore directory, not by an exclude
    entry — deliberately, because that is the mechanism with no prefix trap.
    """
    hidden = os.path.join(HERE, "_unpublished_feeds")
    if not os.path.isdir(hidden):
        pytest.skip("_unpublished_feeds/ not present on this revision")
    names = os.listdir(hidden)
    assert names, "_unpublished_feeds/ exists but is empty"
    for stray in ("feed", "newsletter-feed.xml"):
        assert stray not in os.listdir(HERE), f"{stray} is back at the site root and would serve"
