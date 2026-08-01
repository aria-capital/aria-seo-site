"""
Tests for normalize_monetization_ids.py.

This script rewrites the publisher ID on all 1,460 pages. A regex that is too greedy
would rewrite numbers inside article prose; one that is too narrow would silently miss
ad tags and leave the site unauthorized. Both failure modes are invisible without tests.
"""
import normalize_monetization_ids as norm

REAL_PUB = norm.REAL_ADSENSE_PUB
REAL_TAG = norm.REAL_AMAZON_TAG
WRONG_PUB = norm.WRONG_ADSENSE_PUBS[0]
WRONG_TAG = norm.WRONG_AMAZON_TAGS[0]


def test_adsense_id_is_rewritten_in_script_tag():
    text = f'<script src="...client=ca-pub-{WRONG_PUB}"></script>'
    out, counts = norm.normalize(text)
    assert f"ca-pub-{REAL_PUB}" in out
    assert WRONG_PUB not in out
    assert counts[f"adsense:{WRONG_PUB}"] == 1


def test_adsense_id_is_rewritten_in_ads_txt_form():
    out, _ = norm.normalize(f"google.com, pub-{WRONG_PUB}, DIRECT, f08c47fec0942fa0")
    assert f"pub-{REAL_PUB}" in out


def test_every_occurrence_on_a_page_is_rewritten():
    text = f"ca-pub-{WRONG_PUB} ... ca-pub-{WRONG_PUB} ... ca-pub-{WRONG_PUB}"
    out, counts = norm.normalize(text)
    assert WRONG_PUB not in out
    assert counts[f"adsense:{WRONG_PUB}"] == 3


def test_bare_number_in_prose_is_not_rewritten():
    """Without the pub- prefix requirement, article text could be silently corrupted."""
    text = f"<p>The winning lottery number was {WRONG_PUB} last year.</p>"
    out, counts = norm.normalize(text)
    assert out == text
    assert counts == {}


def test_correct_adsense_id_is_left_alone():
    text = f'client=ca-pub-{REAL_PUB}'
    out, counts = norm.normalize(text)
    assert out == text and counts == {}


def test_amazon_tag_is_rewritten_for_both_separators():
    for sep in ("?", "&"):
        text = f'<a href="https://www.amazon.com/s?k=x{sep}tag={WRONG_TAG}">buy</a>'
        out, counts = norm.normalize(text)
        assert f"tag={REAL_TAG}" in out
        assert WRONG_TAG not in out
        assert counts[f"amazon:{WRONG_TAG}"] == 1


def test_correct_amazon_tag_is_left_alone():
    text = f'<a href="https://www.amazon.com/s?k=x&tag={REAL_TAG}">buy</a>'
    out, counts = norm.normalize(text)
    assert out == text and counts == {}


def test_tag_is_word_boundaried():
    """A longer tag that merely starts with the wrong one must not be truncated."""
    text = f"?tag={WRONG_TAG}extra"
    out, _ = norm.normalize(text)
    assert out == text


def test_unrelated_tag_parameter_is_untouched():
    text = "?tag=someone-elses-99"
    out, counts = norm.normalize(text)
    assert out == text and counts == {}


def test_normalize_is_idempotent():
    text = f'ca-pub-{WRONG_PUB} and ?tag={WRONG_TAG}'
    once, _ = norm.normalize(text)
    twice, counts = norm.normalize(once)
    assert twice == once
    assert counts == {}


def test_both_identities_are_fixed_in_one_pass():
    text = f'<script>ca-pub-{WRONG_PUB}</script><a href="x?tag={WRONG_TAG}">y</a>'
    out, counts = norm.normalize(text)
    assert REAL_PUB in out and REAL_TAG in out
    assert set(counts) == {f"adsense:{WRONG_PUB}", f"amazon:{WRONG_TAG}"}


def test_the_real_ids_are_the_ones_ads_txt_authorizes():
    """
    Guards the whole point of the script: the publisher the pages serve must be the
    publisher ads.txt declares, or the inventory reads as unauthorized.

    NOTE: the ads.txt in this repo is at a project SUBPATH and no crawler fetches it.
    The authoritative file is at the root of the host (aria-capital.github.io/ads.txt),
    which lives in a different repository. This test keeps the local copy consistent so it
    stops being misleading evidence — see test_local_ads_txt_is_not_treated_as_authoritative.
    """
    import os

    ads = open(os.path.join(norm.HERE, "ads.txt"), encoding="utf-8").read()
    assert f"pub-{REAL_PUB}" in ads
    for wrong in norm.WRONG_ADSENSE_PUBS:
        assert wrong not in ads


def test_local_ads_txt_is_not_treated_as_authoritative():
    """
    Regression test for a real mistake: an earlier revision read the subpath ads.txt,
    concluded the other publisher was authoritative, and rewrote all 1,460 pages away
    from the account the crawled root ads.txt actually authorizes.

    The docstring must keep saying where the real file lives, so the next person does not
    repeat it. Verified once by fetching both:
        https://aria-capital.github.io/ads.txt               -> 5576001602612111
        https://aria-capital.github.io/aria-seo-site/ads.txt -> was 6510170611627184
    """
    doc = norm.__doc__
    assert "ROOT OF THE HOST" in doc.upper()
    assert "DIFFERENT repository" in doc or "different repository" in doc


def test_every_page_serves_exactly_one_publisher_id():
    """A corpus split across two publisher IDs is the bug this script exists to prevent."""
    import os
    import re

    found = set()
    for name in sorted(os.listdir(norm.HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(norm.HERE, name), encoding="utf-8", errors="replace") as fh:
            found.update(re.findall(r"ca-pub-(\d+)", fh.read()))
    assert found in ({REAL_PUB}, set()), f"corpus serves multiple publisher IDs: {found}"
