"""
Tests for generate_sitemap.py.

The base URL is assembled from _config.yml and stamped onto every URL in the
sitemap, so a parsing slip mislabels the entire site to crawlers. read_base_url now
REFUSES rather than falling back to a guessed host, and that refusal is pinned below.

generate_sitemap is also one of the three legacy sitemap writers that
safe_write_sitemap() now turns away — see tests/test_sitemap_guard.py. Its selection and
priority logic is still worth testing, so the build() tests opt through the guard
explicitly via the allow_sitemap_write fixture. Nothing here should ever add curated=True
to generate_sitemap itself.
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


@pytest.fixture
def allow_sitemap_write(monkeypatch):
    """
    Let build() complete so its OUTPUT can be asserted on.

    safe_write_sitemap refuses generate_sitemap by design — that refusal is the guard, and
    test_sitemap_guard.py pins it. These tests are about which URLs and priorities build()
    chooses, which is a separate question, so they let the write through here rather than
    weakening the guard in the source.
    """
    import safe_write

    real = safe_write.safe_write_sitemap
    monkeypatch.setattr(
        gs, "safe_write_sitemap", lambda path, content="", **kw: real(path, content, curated=True)
    )


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


def test_missing_config_refuses_rather_than_guessing_a_host(site):
    """
    There used to be a fallback to https://carlostrujillo.github.io — a host the site has
    never been served from, and dead for Pages since the July 2026 org rename. A missing
    config would have written 1,461 <loc>s at a domain that does not resolve, and no
    downstream check would have noticed: check_site_integrity only verifies that each
    <loc>'s slug maps to a real local file, which is true regardless of the host.
    """
    with pytest.raises(SystemExit):
        gs.read_base_url()


def test_config_without_a_url_key_also_refuses(site):
    (site / "_config.yml").write_text("baseurl: /my-site\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        gs.read_base_url()


# --- build() ----------------------------------------------------------------


def test_build_lists_articles_and_writes_robots(site, allow_sitemap_write):
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


def test_build_excludes_error_and_verification_pages(site, allow_sitemap_write):
    _config(site, "url: https://example.test\n")
    for name in ("404.html", "google-verify.html", "real.html"):
        (site / name).write_text(
            "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
        )

    count, _ = gs.build()
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")

    assert count == 1
    assert "404.html" not in sitemap and "google-verify.html" not in sitemap


def test_build_gives_static_pages_low_priority(site, allow_sitemap_write):
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


def test_build_is_refused_without_the_fixture(site):
    """
    The guard, seen from this module: without an explicit opt-in, generate_sitemap cannot
    replace the curated sitemap — not even by accident, and not even when a session calls
    build() merely to inspect what it would produce. That exact mistake rewrote the live
    sitemap once.
    """
    from check_site_integrity import IntegrityError

    _config(site, "url: https://example.test\n")
    (site / "real.html").write_text(
        "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
    )
    with pytest.raises(IntegrityError, match="Refusing to write"):
        gs.build()
