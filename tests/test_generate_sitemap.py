"""
Tests for generate_sitemap.py.

The base URL is assembled from _config.yml and stamped onto every URL in the
sitemap, so a parsing slip mislabels the entire site to crawlers. There is also a
hardcoded fallback host that no longer matches the deployed one — pinned here so
the discrepancy is visible rather than silent.
"""
import pytest

import check_site_integrity as csi
import generate_sitemap as gs


@pytest.fixture
def site(tmp_path, monkeypatch):
    """Point both the generator and the validator at an isolated site dir."""
    monkeypatch.setattr(gs, "HERE", tmp_path)
    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    return tmp_path


def _config(site, text):
    (site / "_config.yml").write_text(text, encoding="utf-8")


def test_url_and_baseurl_are_joined(site):
    _config(site, "url: https://example.test\nbaseurl: /my-site\n")
    assert gs.read_base_url() == "https://example.test/my-site/"


def test_trailing_slash_on_url_is_not_doubled(site):
    _config(site, "url: https://example.test/\nbaseurl: /my-site\n")
    assert gs.read_base_url() == "https://example.test/my-site/"


def test_baseurl_without_leading_slash_is_normalized(site):
    _config(site, "url: https://example.test\nbaseurl: my-site\n")
    assert gs.read_base_url() == "https://example.test/my-site/"


def test_quoted_baseurl_is_unquoted(site):
    _config(site, 'url: https://example.test\nbaseurl: "/my-site"\n')
    assert gs.read_base_url() == "https://example.test/my-site/"


def test_url_alone_yields_bare_host(site):
    _config(site, "url: https://example.test\n")
    assert gs.read_base_url() == "https://example.test/"


def test_commented_url_is_not_picked_up(site):
    """The regex is line-anchored; a commented key must not win."""
    _config(site, "# url: https://wrong.test\nurl: https://example.test\n")
    assert gs.read_base_url() == "https://example.test/"


def test_missing_config_falls_back_to_hardcoded_host(site):
    """
    Documents a live discrepancy: the fallback host is not the deployed host
    (_config.yml says aria-capital.github.io). If _config.yml ever goes missing,
    the whole sitemap silently points at a domain the site does not live on.
    """
    assert gs.read_base_url() == "https://carlostrujillo.github.io/"


# --- build() ----------------------------------------------------------------


def test_build_lists_articles_and_writes_robots(site):
    _config(site, "url: https://example.test\nbaseurl: /s\n")
    for name in ("index.html", "guide.html"):
        (site / name).write_text(
            "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
        )

    count, base = gs.build()

    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert count == 2 and base == "https://example.test/s/"
    assert "<loc>https://example.test/s/guide.html</loc>" in sitemap
    # The homepage is emitted as the clean root URL, not index.html.
    assert "<loc>https://example.test/s/</loc>" in sitemap
    assert "/s/index.html" not in sitemap
    assert (site / "robots.txt").read_text(encoding="utf-8").endswith(
        "Sitemap: https://example.test/s/sitemap.xml\n")


def test_build_excludes_error_and_verification_pages(site):
    _config(site, "url: https://example.test\n")
    for name in ("404.html", "google-verify.html", "real.html"):
        (site / name).write_text(
            "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
        )

    count, _ = gs.build()
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")

    assert count == 1
    assert "404.html" not in sitemap and "google-verify.html" not in sitemap


def test_build_gives_static_pages_low_priority(site):
    _config(site, "url: https://example.test\n")
    for name in ("privacy.html", "guide.html"):
        (site / name).write_text(
            "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
        )

    gs.build()
    rows = (site / "sitemap.xml").read_text(encoding="utf-8").splitlines()
    privacy = next(r for r in rows if "privacy.html" in r)
    guide = next(r for r in rows if "guide.html" in r)

    assert "<priority>0.3</priority>" in privacy
    assert "<priority>0.8</priority>" in guide
