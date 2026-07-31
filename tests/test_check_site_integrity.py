"""
Tests for check_site_integrity.py — the definition of "what is corrupt".

Every other guard in the repo defers to this module, so its edge cases are worth
pinning down: safe_write reuses it as a validator and the CI corpus gate reuses
its severity metrics.
"""
import pytest

from check_site_integrity import (
    check_html_closed,
    check_sitemap,
    html_severity,
    severity_regressions,
)

GOOD = "<html><head></head><body><div>ok</div></body></html>"


def test_clean_document_has_no_problems(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(GOOD, encoding="utf-8")
    assert check_html_closed(str(p)) == []


def test_missing_file_is_reported(tmp_path):
    problems = check_html_closed(str(tmp_path / "nope.html"))
    assert len(problems) == 1 and "does not exist" in problems[0]


def test_empty_file_is_reported(tmp_path):
    p = tmp_path / "a.html"
    p.write_text("   \n", encoding="utf-8")
    problems = check_html_closed(str(p))
    assert len(problems) == 1 and "is empty" in problems[0]


def test_truncated_document_is_reported(tmp_path):
    p = tmp_path / "a.html"
    p.write_text("<html><head></head><body><div>cut", encoding="utf-8")
    assert any("does NOT end with </html>" in x for x in check_html_closed(str(p)))


def test_div_imbalance_is_reported(tmp_path):
    p = tmp_path / "a.html"
    p.write_text(
        "<html><head></head><body><div><div>x</div></body></html>", encoding="utf-8"
    )
    assert any("imbalance" in x for x in check_html_closed(str(p)))


def test_div_matching_is_word_boundaried(tmp_path):
    """<divider> is not a <div>; a naive substring match would miscount it."""
    p = tmp_path / "a.html"
    p.write_text(
        "<html><head></head><body><divider></divider><div>x</div></body></html>",
        encoding="utf-8",
    )
    assert not any("imbalance" in x for x in check_html_closed(str(p)))


# --- severity metrics -------------------------------------------------------


def test_severity_of_clean_document_is_all_zero():
    assert not any(html_severity(GOOD).values())


def test_severity_counts_each_kind_of_damage():
    sev = html_severity("<html><head></head><body><div><div>")
    assert sev["unterminated"] is True
    assert sev["div_delta"] == 2
    assert sev["tag_errors"] == 2  # missing </body> and </html>


def test_severity_detects_unterminated_attribute():
    """The cookie-banner bug: a style attribute cut off mid-value."""
    cut = '<html><head></head><body><div style="color:#fff;display:fl'
    assert html_severity(cut)["unterminated_attr"] == 1
    assert html_severity(GOOD)["unterminated_attr"] == 0


def test_no_regressions_between_identical_severities():
    assert severity_regressions(html_severity(GOOD), html_severity(GOOD)) == []


def test_regression_reported_only_when_a_metric_rises():
    before = {"div_delta": 2, "tag_errors": 1}
    assert severity_regressions(before, {"div_delta": 3, "tag_errors": 1}) == ["div_delta: 2 -> 3"]
    assert severity_regressions(before, {"div_delta": 1, "tag_errors": 0}) == []


def test_missing_metric_is_treated_as_zero():
    """A file with no baseline entry is held to the clean standard."""
    assert severity_regressions({}, {"div_delta": 1}) == ["div_delta: 0 -> 1"]
    assert severity_regressions({}, {"div_delta": 0}) == []


# --- sitemap ----------------------------------------------------------------


def test_sitemap_flags_missing_loc_entries(tmp_path, monkeypatch):
    import check_site_integrity as csi

    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    p = tmp_path / "sitemap.xml"
    p.write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "</urlset>",
        encoding="utf-8",
    )
    assert any("no <loc> entries" in x for x in check_sitemap(str(p)))


def test_sitemap_ignores_directory_urls(tmp_path, monkeypatch):
    """A root/clean URL has no local file to map, and must not be reported."""
    import check_site_integrity as csi

    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    p = tmp_path / "sitemap.xml"
    p.write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://x.test/</loc></url></urlset>",
        encoding="utf-8",
    )
    assert check_sitemap(str(p)) == []
