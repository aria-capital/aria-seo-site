"""
Tests for safe_write.py — the validated atomic write path.

These cover the property the whole module exists for: a truncated buffer must
never become the live file. The module shipped with a --selftest that covered
the happy path and one rejection; these add the branches that were untested and
that the mutators now depend on (the no-regression mode, sitemap writes, temp
cleanup, index detection).
"""
import os

import pytest

from check_site_integrity import IntegrityError
from safe_write import safe_write_html, safe_write_sitemap, safe_write_text

GOOD = "<html><head></head><body><div>ok</div></body></html>"
TRUNCATED = "<html><head></head><body><div><a href='x.html'>card"


def _leftover_temps(d):
    return [f for f in os.listdir(d) if f.endswith(".tmp")]


def test_valid_html_write_lands(tmp_path):
    p = tmp_path / "article.html"
    safe_write_html(str(p), GOOD)
    assert p.read_text(encoding="utf-8") == GOOD


def test_truncated_write_is_refused(tmp_path):
    p = tmp_path / "article.html"
    with pytest.raises(IntegrityError):
        safe_write_html(str(p), TRUNCATED)
    assert not p.exists(), "a refused write must not create the file"


def test_refused_write_leaves_original_intact(tmp_path):
    p = tmp_path / "article.html"
    safe_write_html(str(p), GOOD)
    with pytest.raises(IntegrityError):
        safe_write_html(str(p), TRUNCATED)
    assert p.read_text(encoding="utf-8") == GOOD


def test_refused_write_cleans_up_temp_file(tmp_path):
    p = tmp_path / "article.html"
    with pytest.raises(IntegrityError):
        safe_write_html(str(p), TRUNCATED)
    assert _leftover_temps(tmp_path) == []


def test_validator_exception_still_cleans_up_temp(tmp_path):
    """A validator that raises must not leak the temp file either."""
    p = tmp_path / "thing.txt"

    def boom(_path):
        raise RuntimeError("validator exploded")

    with pytest.raises(RuntimeError):
        safe_write_text(str(p), "content", validator=boom)
    assert _leftover_temps(tmp_path) == []


def test_safe_write_text_without_validator_is_still_atomic(tmp_path):
    p = tmp_path / "notes.txt"
    safe_write_text(str(p), "hello")
    assert p.read_text(encoding="utf-8") == "hello"
    assert _leftover_temps(tmp_path) == []


def test_index_html_gets_index_specific_checks(tmp_path):
    """index.html must fail on a broken card link; a plain article must not."""
    broken_card = (
        '<html><head></head><body><div><a href="does-not-exist.html">x</a></div>'
        "<footer></footer></body></html>"
    )
    article = tmp_path / "article.html"
    safe_write_html(str(article), broken_card)  # generic check ignores links

    index = tmp_path / "index.html"
    with pytest.raises(IntegrityError, match="broken card link"):
        safe_write_html(str(index), broken_card)


# --- no-regression mode -----------------------------------------------------
# The mutators run over a corpus that is already ~30% damaged. Strict validation
# would refuse every edit to those files, so they gate on "no worse" instead.

DAMAGED = "<html><head></head><body><div><div></div>"  # unterminated + 1 open div


def test_no_regression_allows_edit_that_keeps_damage_equal(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(DAMAGED, encoding="utf-8")
    edited = DAMAGED.replace("<body>", "<body><p>added</p>")
    safe_write_html(str(p), edited, allow_preexisting=True)
    assert p.read_text(encoding="utf-8") == edited


def test_no_regression_refuses_edit_that_worsens_damage(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(DAMAGED, encoding="utf-8")
    worse = DAMAGED + "<div>"  # div_delta 1 -> 2
    with pytest.raises(IntegrityError, match="worse"):
        safe_write_html(str(p), worse, allow_preexisting=True)
    assert p.read_text(encoding="utf-8") == DAMAGED


def test_no_regression_allows_a_full_repair(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(DAMAGED, encoding="utf-8")
    safe_write_html(str(p), GOOD, allow_preexisting=True)
    assert p.read_text(encoding="utf-8") == GOOD


def test_no_regression_still_requires_new_files_to_be_clean(tmp_path):
    """There is no pre-existing damage to grandfather, so strict rules apply."""
    p = tmp_path / "brand-new.html"
    with pytest.raises(IntegrityError):
        safe_write_html(str(p), TRUNCATED, allow_preexisting=True)
    assert not p.exists()


# --- sitemap ----------------------------------------------------------------

SITEMAP_TMPL = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "{rows}\n</urlset>\n"
)


def test_sitemap_write_lands_when_locs_resolve(tmp_path, monkeypatch):
    import check_site_integrity as csi

    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    (tmp_path / "real.html").write_text(GOOD, encoding="utf-8")
    xml = SITEMAP_TMPL.format(rows="  <url><loc>https://x.test/real.html</loc></url>")
    out = tmp_path / "sitemap.xml"
    # curated=True throughout this section: these tests cover the atomic-write and
    # validation mechanics, not the curation policy that the flag enforces.
    safe_write_sitemap(str(out), xml, curated=True)
    assert out.exists()


def test_sitemap_write_refuses_invalid_xml(tmp_path):
    out = tmp_path / "sitemap.xml"
    with pytest.raises(IntegrityError, match="invalid XML"):
        safe_write_sitemap(str(out), "<urlset><url></urlset>", curated=True)
    assert not out.exists()


def test_sitemap_write_refuses_dangling_loc(tmp_path, monkeypatch):
    import check_site_integrity as csi

    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    xml = SITEMAP_TMPL.format(rows="  <url><loc>https://x.test/ghost.html</loc></url>")
    out = tmp_path / "sitemap.xml"
    with pytest.raises(IntegrityError, match="missing file"):
        safe_write_sitemap(str(out), xml, curated=True)
    assert not out.exists()
