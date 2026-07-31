"""
Tests for inject_affiliate_links.py.

This script rewrites articles in bulk and claims idempotency in its docstring;
nothing verified it. A non-idempotent injector stacks a duplicate CTA box onto
every matching article each time it runs, which is both a visible defect and an
FTC-disclosure problem.
"""
import pytest

import inject_affiliate_links as inj

ARTICLE = (
    "<html><head></head><body>\n"
    "<h1>Student loan refinancing for nurses</h1>\n"
    "<p>Talk about pslf and loan forgiveness nurse options.</p>\n"
    "<footer>f</footer>\n"
    "</body></html>"
)


# --- pure helpers -----------------------------------------------------------


def test_injection_point_prefers_footer_over_body():
    content = "<html><body>x<footer>f</footer></body></html>"
    assert inj.find_injection_point(content) == content.index("<footer")


def test_injection_point_falls_back_to_body_close():
    content = "<html><body>x</body></html>"
    assert inj.find_injection_point(content) == content.index("</body>")


def test_injection_point_is_none_without_an_anchor():
    assert inj.find_injection_point("<html>no anchors here</html>") is None


def test_content_with_no_anchor_is_returned_unchanged():
    content = "<html>no anchors here</html>"
    assert inj.inject_into_content(content, ["<div>cta</div>"]) == content


def test_already_has_cta_matches_only_its_own_affiliate():
    content = "<!-- AFFILIATE-CTA:sofi -->"
    assert inj.already_has_cta(content, "sofi")
    assert not inj.already_has_cta(content, "credible")


def test_keyword_matching_is_substring_based():
    assert inj.content_matches_affiliate("about pslf rules", ["pslf"])
    assert not inj.content_matches_affiliate("about pensions", ["pslf"])


@pytest.mark.parametrize("name", ["index.html", "about.html", "privacy.html", "404.html"])
def test_meta_pages_are_not_articles(name):
    assert not inj.is_article_file(name)


def test_ordinary_article_is_an_article():
    assert inj.is_article_file("/site/nurse-loan-guide-2026.html")


def test_every_affiliate_block_is_html_balanced():
    """A malformed CTA template would corrupt every article it touches."""
    import re

    for aff in inj.AFFILIATES:
        block = inj.build_cta_block(aff)
        assert len(re.findall(r"<div\b", block)) == block.count("</div>")
        assert block.count("<p") == block.count("</p>")
        assert "<!-- AFFILIATE-CTA:{} -->".format(aff["id"]) in block


def test_affiliate_ids_are_unique():
    ids = [a["id"] for a in inj.AFFILIATES]
    assert len(ids) == len(set(ids))


def test_outbound_affiliate_links_are_disclosed_to_crawlers():
    """Undisclosed paid links are a search-penalty and FTC risk."""
    for aff in inj.AFFILIATES:
        assert 'rel="nofollow sponsored"' in aff["cta_text"]


# --- end-to-end -------------------------------------------------------------


@pytest.fixture
def site(tmp_path, monkeypatch):
    (tmp_path / "loan-guide-2026.html").write_text(ARTICLE, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["inject_affiliate_links.py", "--dir", str(tmp_path)])
    return tmp_path


def test_injection_adds_a_cta_before_the_footer(site):
    inj.main()
    out = (site / "loan-guide-2026.html").read_text(encoding="utf-8")
    assert "<!-- AFFILIATE-CTA:sofi -->" in out
    assert out.index("AFFILIATE-CTA") < out.index("<footer")


def test_injection_is_idempotent(site):
    inj.main()
    once = (site / "loan-guide-2026.html").read_text(encoding="utf-8")
    inj.main()
    twice = (site / "loan-guide-2026.html").read_text(encoding="utf-8")
    assert once == twice, "a second run must not stack another CTA"


def test_injection_does_not_corrupt_the_document(site):
    import re

    inj.main()
    out = (site / "loan-guide-2026.html").read_text(encoding="utf-8")
    assert out.rstrip().endswith("</html>")
    assert len(re.findall(r"<div\b", out)) == out.count("</div>")


def test_non_matching_article_is_left_byte_identical(tmp_path, monkeypatch):
    unrelated = (
        "<html><head></head><body><h1>Sourdough starter</h1>"
        "<footer>f</footer></body></html>"
    )
    p = tmp_path / "bread-2026.html"
    p.write_text(unrelated, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["inject_affiliate_links.py", "--dir", str(tmp_path)])

    inj.main()
    assert p.read_text(encoding="utf-8") == unrelated
