"""
Tests for fix_canonicals.py.

A wrong canonical is worse than a missing one: it actively hands the page to another URL.
Three pages pointed at example.com and one pointed at an unrelated article, which is enough
to de-index them entirely. These pin the add / correct / dedupe / leave-alone decisions.
"""
import pytest

import fix_canonicals as fc

BASE = "https://site.test/base/"
HEAD = "<html><head><title>T</title></head><body><div>x</div></body></html>"


def _tag(url):
    return f'<link rel="canonical" href="{url}">'


def test_missing_canonical_is_added_before_head_close():
    out, action = fc.fix(HEAD, BASE + "a.html")
    assert action == "added"
    assert _tag(BASE + "a.html") in out
    assert out.index("canonical") < out.index("</head>")


def test_correct_canonical_is_left_untouched():
    text = HEAD.replace("</head>", _tag(BASE + "a.html") + "</head>")
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "ok" and out == text


def test_placeholder_host_is_corrected():
    """example.com canonicals hand the page to a domain the owner does not control."""
    text = HEAD.replace("</head>", _tag("https://example.com/a") + "</head>")
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "corrected"
    assert "example.com" not in out
    assert _tag(BASE + "a.html") in out


def test_wrong_host_is_corrected():
    text = HEAD.replace("</head>", _tag("https://otherdomain.test/seo_site/a.html") + "</head>")
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "corrected" and "otherdomain.test" not in out


def test_duplicate_canonicals_are_collapsed_to_one():
    text = HEAD.replace("</head>", _tag(BASE + "a.html") + _tag(BASE + "b.html") + "</head>")
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "deduped"
    assert out.count("rel=\"canonical\"") == 1
    assert _tag(BASE + "a.html") in out


def test_file_without_a_head_is_skipped_not_corrupted():
    text = "<div>fragment with no head</div>"
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "no-head" and out == text


def test_fix_is_idempotent():
    once, _ = fc.fix(HEAD, BASE + "a.html")
    twice, action = fc.fix(once, BASE + "a.html")
    assert action == "ok" and twice == once


def test_index_canonicalises_to_the_clean_root():
    assert fc.expected_url(BASE, "index.html") == BASE
    assert fc.expected_url(BASE, "guide.html") == BASE + "guide.html"


def test_allowlisted_cross_canonical_is_preserved(monkeypatch):
    """
    Two genuine near-duplicates may nominate one as authoritative. Forcing self-canonical
    would destroy that, so allowlisted pairs keep pointing at their chosen target.
    """
    monkeypatch.setattr(fc, "CROSS_CANONICAL_ALLOWLIST", {"dupe.html": "primary.html"})
    assert fc.expected_url(BASE, "dupe.html") == BASE + "primary.html"


def test_unallowlisted_cross_canonical_is_corrected_to_self():
    text = HEAD.replace("</head>", _tag(BASE + "unrelated-article.html") + "</head>")
    out, action = fc.fix(text, BASE + "a.html")
    assert action == "corrected"
    assert _tag(BASE + "a.html") in out


# --- corpus-level invariant -------------------------------------------------


def test_every_live_page_has_exactly_one_on_host_canonical():
    """The whole point of the script, asserted against the real corpus."""
    import os
    import re

    base = fc.read_base_url()

    # WALK, do not listdir. This assertion read as "every live page has exactly one
    # on-host canonical" while the 15 pages under pet_care/ had NO canonical tag at
    # all — because both the script and this test scanned the repo root only. The
    # flat scan is what let a whole directory ship unprocessed and still go green.
    files = []
    for dirpath, dirnames, filenames in os.walk(fc.HERE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "tests", "store-covers")]
        for f in filenames:
            if not f.endswith(".html"):
                continue
            name = os.path.relpath(os.path.join(dirpath, f), fc.HERE)
            if name in fc.SKIP or os.path.basename(name) in fc.SKIP:
                continue
            files.append(name)
    files.sort()
    assert files, "no pages found"
    assert any(os.sep in n for n in files), "scan is not reaching subdirectories"

    offenders = []
    for name in files:
        with open(os.path.join(fc.HERE, name), encoding="utf-8", errors="replace") as fh:
            tags = re.findall(r'<link[^>]+rel="canonical"[^>]*>', fh.read(), re.I)
        if len(tags) != 1 or base not in tags[0]:
            offenders.append(name)
    assert offenders == []
