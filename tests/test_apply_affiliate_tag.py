"""
Tests for apply_affiliate_tag.py.

This script rewrites every Amazon link across ~1,400 files, and the money depends
on it: an untagged link pays $0. Its two pure functions carry all the risk and
had no coverage — in particular the "already tagged" guard, which is the only
thing making a re-run non-destructive.
"""
import pytest

from apply_affiliate_tag import load_tag, tag_url


# --- tag_url ----------------------------------------------------------------


def test_tag_appended_to_bare_url():
    assert tag_url("https://www.amazon.com/dp/B001", "aria-20") == \
        "https://www.amazon.com/dp/B001?tag=aria-20"


def test_tag_appended_with_ampersand_when_query_exists():
    assert tag_url("https://www.amazon.com/s?k=stethoscope", "aria-20") == \
        "https://www.amazon.com/s?k=stethoscope&tag=aria-20"


def test_bare_host_is_normalized_to_www():
    """A bare amazon.com can drop the tag on redirect, so the host is rewritten."""
    assert tag_url("https://amazon.com/dp/B001", "aria-20").startswith(
        "https://www.amazon.com/")


def test_http_is_upgraded_to_https():
    assert tag_url("http://amazon.com/dp/B001", "aria-20").startswith("https://www.")


def test_already_tagged_url_is_untouched():
    """Idempotency: re-running the script must not double-tag."""
    url = "https://www.amazon.com/s?k=books&tag=aria-20"
    assert tag_url(url, "other-20") == url


def test_tag_as_only_query_param_is_detected():
    url = "https://www.amazon.com/dp/B001?tag=aria-20"
    assert tag_url(url, "other-20") == url


def test_tag_is_not_confused_by_a_similarly_named_param():
    """`?hashtag=` contains 'tag=' but is not the associate tag."""
    out = tag_url("https://www.amazon.com/s?hashtag=x", "aria-20")
    assert out.endswith("&tag=aria-20")


# --- load_tag ---------------------------------------------------------------


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "real-20")
    assert load_tag() == "real-20"


@pytest.mark.parametrize("placeholder", ["yourtag-20", "your-tag", "your_tag_here", "name-20", ""])
def test_placeholders_are_rejected(monkeypatch, placeholder, tmp_path):
    """A placeholder must read as 'unset', or the script would tag every link with junk."""
    monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", placeholder)
    monkeypatch.setattr("apply_affiliate_tag.ENV_FILE", tmp_path / "missing.env")
    assert load_tag() == ""


def test_tag_is_read_from_env_file_when_var_unset(monkeypatch, tmp_path):
    env = tmp_path / ".env.aria"
    env.write_text('AMAZON_ASSOCIATE_TAG="fromfile-20"\n', encoding="utf-8")
    monkeypatch.delenv("AMAZON_ASSOCIATE_TAG", raising=False)
    monkeypatch.setattr("apply_affiliate_tag.ENV_FILE", env)
    assert load_tag() == "fromfile-20"


def test_commented_out_line_in_env_file_is_ignored(monkeypatch, tmp_path):
    env = tmp_path / ".env.aria"
    env.write_text("# AMAZON_ASSOCIATE_TAG=commented-20\n", encoding="utf-8")
    monkeypatch.delenv("AMAZON_ASSOCIATE_TAG", raising=False)
    monkeypatch.setattr("apply_affiliate_tag.ENV_FILE", env)
    assert load_tag() == ""


def test_missing_env_file_yields_empty_tag(monkeypatch, tmp_path):
    monkeypatch.delenv("AMAZON_ASSOCIATE_TAG", raising=False)
    monkeypatch.setattr("apply_affiliate_tag.ENV_FILE", tmp_path / "nope.env")
    assert load_tag() == ""
