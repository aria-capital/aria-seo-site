"""
Tests for strip_false_credentials.py.

This edits published copy on 64 pages, so both failure directions are costly: leaving a
false clinical-review claim live is the legal exposure the script exists to remove, while
over-matching would silently rewrite legitimate article prose. Both are pinned here.
"""
import re

from strip_false_credentials import strip_claims


def _one(text):
    out, n = strip_claims(text)
    return out


# --- the four contexts a claim appears in -----------------------------------


def test_title_parenthetical_is_removed():
    out = _one("<title>Best Medical AI Apps (Reviewed by an ICU RN) | ICU Notebook</title>")
    assert out == "<title>Best Medical AI Apps | ICU Notebook</title>"


def test_title_dash_suffix_is_removed():
    out = _one("<title>Best Gift Ideas for Nurses 2026 — From a Working ICU Nurse</title>")
    assert out == "<title>Best Gift Ideas for Nurses 2026</title>"


def test_meta_description_trailing_sentence_is_removed():
    out = _one('<meta name="description" content="Journals for grief and sleep. Reviewed by a working ICU nurse.">')
    assert out == '<meta name="description" content="Journals for grief and sleep.">'


def test_body_leading_sentence_is_removed():
    out = _one("<p><em>Written by an ICU nurse on the CRNA path. See also: more</em></p>")
    assert out == "<p><em>See also: more</em></p>"


def test_byline_separator_is_removed():
    out = _one("<p>CRNA path &middot; Updated 2026 &middot; Written from the ICU nurse's perspective</p>")
    assert out == "<p>CRNA path &middot; Updated 2026</p>"


def test_comma_appositive_is_removed_with_its_comma():
    out = _one("<p>useful in the chart room, ranked by a working ICU nurse.</p>")
    assert out == "<p>useful in the chart room.</p>"


def test_participle_is_removed_without_stranding_a_space():
    out = _one("<p>Practical, thoughtful picks chosen by a working ICU nurse. No fluff.</p>")
    assert out == "<p>Practical, thoughtful picks. No fluff.</p>"


# --- grammar preservation ---------------------------------------------------


def test_no_space_is_left_before_punctuation():
    assert " ." not in _one("<p>Some picks chosen by a working ICU nurse.</p>")


def test_no_empty_parenthetical_is_left_behind():
    assert "()" not in _one("<title>Guide (Reviewed by an ICU RN) | X</title>")


def test_ungrammatical_deletion_is_rewritten_instead():
    """Deleting mid-clause would leave 'was to help'; the clause is rewritten."""
    out = _one("<p>Nurse Financial Freedom was built by healthcare and finance professionals to help nurses.</p>")
    assert out == "<p>Nurse Financial Freedom was built to help nurses.</p>"


def test_bolded_lead_in_is_replaced_not_emptied():
    out = _one("<p><strong>Written from the bedside:</strong> These are the apps.</p>")
    assert "<strong></strong>" not in out
    assert "<strong>Worth knowing:</strong>" in out


# --- things that must NOT be touched ----------------------------------------


def test_cookie_banner_copy_is_untouched():
    """'We use cookies' appears on 756 pages and must never be rewritten."""
    banner = "<span>We use cookies for analytics and advertising (Google AdSense).</span>"
    assert _one(banner) == banner


def test_advice_to_consult_an_attorney_is_untouched():
    text = "<p>Have the contract reviewed by a qualified nursing law attorney.</p>"
    assert _one(text) == text


def test_description_of_a_review_committee_is_untouched():
    text = "<p>Applications are reviewed by a committee that includes nurses.</p>"
    assert _one(text) == text


def test_site_identity_statement_is_untouched():
    """
    contact.html names a real person. Only the owner knows if it is accurate, and removing
    a true self-description would be its own kind of wrong.
    """
    text = ("<p>ICU Notebook is written by Carlos — an ICU nurse building passive income "
            "on the side while working toward CRNA school.</p>")
    assert _one(text) == text


def test_clinical_prose_beginning_with_from_a_is_untouched():
    text = "<p>Bleeding from a tracheostomy can herald catastrophic arterial injury.</p>"
    assert _one(text) == text


def test_your_team_is_not_matched_as_our_team():
    text = "<p>Advocacy within your team for open conversation about futility.</p>"
    assert _one(text) == text


# --- invariants -------------------------------------------------------------


def test_strip_is_idempotent():
    text = "<title>Guide (Reviewed by an ICU RN) | X</title>"
    once = _one(text)
    assert _one(once) == once


def test_markup_structure_is_preserved():
    text = ('<title>A (Reviewed by an ICU RN) | X</title>'
            '<meta name="description" content="Body. Reviewed by a working ICU nurse.">'
            '<p><em>Written by a CRNA Student. Rest.</em></p>')
    out = _one(text)
    for tag in ("<title>", "</title>", 'content="', "<p>", "</p>", "<em>", "</em>"):
        assert out.count(tag) == text.count(tag)


def test_closing_quote_of_a_meta_attribute_survives_a_dash_suffix():
    """Regression: a greedy dash rule once ate past the end of content="..."."""
    text = '<meta name="description" content="Tools — reviewed and ranked by a working RN."><link rel="x">'
    out = _one(text)
    assert out.count('"') == text.count('"')
    assert "<link rel=" in out


def test_claim_count_is_reported():
    _, n = strip_claims("<title>A (Reviewed by an ICU RN) | X</title>")
    assert n == 1
