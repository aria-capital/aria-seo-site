"""
Tests for depersonalize_site.py.

The site published AI-generated drug-dosing content under a real person's legal name and
nursing credential. That is a licensure exposure, not just a civil one — a Board of Nursing
can act on a licensed nurse publicly disseminating clinical guidance. These tests pin that
the identifiers are gone and stay gone.
"""
import depersonalize_site as D

ENTITY = D.ENTITY


def _one(text):
    out, _ = D.depersonalize(text)
    return out


def test_legal_name_and_credential_are_replaced_with_the_entity():
    text = "<p>Site operated by Carlos Trujillo, an ICU nurse building passive income streams.</p>"
    out = _one(text)
    assert "Carlos Trujillo" not in out
    assert "ICU nurse" not in out
    assert ENTITY in out


def test_personal_byline_is_replaced_with_an_entity_statement():
    text = ("<p>ICU Notebook is written by Carlos — an ICU nurse building passive income on "
            "the side while working toward CRNA school. I write from real experience, not theory.</p>")
    out = _one(text)
    assert "Carlos" not in out
    assert ENTITY in out
    assert "not individually reviewed by a licensed clinician" in out


def test_home_state_leak_is_removed_but_the_sentence_survives():
    """A generator leaked the owner's state into published prose."""
    text = "<p>Arizona (Carlos&#39;s state) is a right-to-work state. Texas too.</p>"
    out = _one(text)
    assert "Carlos" not in out
    assert out == "<p>Arizona is a right-to-work state. Texas too.</p>"


def test_home_state_leak_with_a_plain_apostrophe():
    out = _one("<p>Arizona (Carlos's state) is right-to-work.</p>")
    assert out == "<p>Arizona is right-to-work.</p>"


def test_personal_domain_link_is_repointed_to_the_live_site():
    text = '<a href="https://carlostrujillo.github.io/money-psychology/">library</a>'
    out = _one(text)
    assert "carlostrujillo.github.io" not in out
    assert D.LIVE_SITE in out


def test_bare_personal_domain_text_is_replaced():
    out = _one("<p>Part of the library at carlostrujillo.github.io/money-psychology.</p>")
    assert "carlostrujillo" not in out


def test_bare_full_name_anywhere_is_replaced():
    out = _one("<p>Written by Carlos Trujillo.</p>")
    assert "Carlos Trujillo" not in out and ENTITY in out


def test_business_mailbox_is_deliberately_preserved():
    """
    Rewriting a working mailbox would break contact and unsubscribe links if the
    replacement alias does not exist. Flagged for the owner instead.
    """
    text = '<a href="mailto:carlos@ariacapitalholdings.com">carlos@ariacapitalholdings.com</a>'
    assert _one(text) == text


def test_depersonalize_is_idempotent():
    text = "<p>operated by Carlos Trujillo, an ICU nurse building passive income streams.</p>"
    once = _one(text)
    assert _one(once) == once


def test_replacement_count_is_reported():
    _, n = D.depersonalize("<p>Carlos Trujillo</p><p>Arizona (Carlos's state) rocks.</p>")
    assert n == 2


# --- corpus-level invariant -------------------------------------------------


def test_no_personal_identifiers_remain_on_the_live_site():
    """The mailto business address is the only permitted occurrence of the name."""
    import os
    import re

    banned = [
        re.compile(r"Carlos Trujillo"),
        re.compile(r"Carlos(?:&#39;|')s state"),
        re.compile(r"carlostrujillo\.github\.io"),
        re.compile(r"written by Carlos", re.I),
    ]
    offenders = []
    for name in sorted(os.listdir(D.HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(D.HERE, name), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for pattern in banned:
            if pattern.search(text):
                offenders.append(f"{name}: {pattern.pattern}")
    assert offenders == []
