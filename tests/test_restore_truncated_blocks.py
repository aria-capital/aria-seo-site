"""
Tests for restore_truncated_blocks.py.

This is the only repair in the repo that puts article PROSE back on the page, so the guard
around it is the whole point: a tail is spliced only at a single unambiguous anchor, and
only ever appended at the point where the write stopped. If the anchor is missing or
appears twice, nothing happens.

The corpus-level tests at the bottom check the two things a bad restoration would show up
as: a page still cut off mid-word, or a resurrected dead link.
"""
import os
import re

import restore_truncated_blocks as R

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENTRY = R.Restoration("x.html", anchor="<li>Save the number for your nea", tail="rest</li>\n</ol>")


def test_the_tail_lands_immediately_after_the_anchor():
    out = R.apply("<ol>\n<li>Save the number for your nea\n<div>after</div>", ENTRY)
    assert out == "<ol>\n<li>Save the number for your nearest</li>\n</ol>\n<div>after</div>"


def test_nothing_happens_when_the_anchor_is_absent():
    assert R.apply("<ol>\n<li>unrelated</li>\n</ol>", ENTRY) is None


def test_nothing_happens_when_the_anchor_is_ambiguous():
    """Two matches means the cut point is not identified, so the repair declines."""
    doc = "<li>Save the number for your nea\n<li>Save the number for your nea"
    assert R.apply(doc, ENTRY) is None


def test_apply_is_idempotent():
    once = R.apply("<ol>\n<li>Save the number for your nea\n", ENTRY)
    assert once is not None
    assert R.apply(once, ENTRY) is None


def test_block_balance_reports_each_tag():
    assert R.block_balance("<ol><li>a</li>")["ol"] == 1
    assert R.block_balance("<ol><li>a</li></ol>")["ol"] == 0


def test_every_entry_closes_the_block_it_restores():
    """A tail that does not restore the balance would leave the page no better off."""
    for entry in R.RESTORATIONS:
        path = os.path.join(HERE, entry.filename)
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        assert entry.anchor in html, entry.filename
        assert all(v == 0 for v in R.block_balance(html).values()), entry.filename


def test_every_entry_is_already_applied_to_the_live_corpus():
    for entry in R.RESTORATIONS:
        with open(os.path.join(HERE, entry.filename), encoding="utf-8") as fh:
            html = fh.read()
        assert R.apply(html, entry) is None, f"{entry.filename} is not restored"


# --- what must NOT come back with the prose ----------------------------------


def test_no_restored_tail_reintroduces_a_placeholder_link():
    """
    The historical revisions also hold `href="#"` cards and a #GUMROAD_… CTA. Restoring
    those would republish dead links, so every tail is cut before them.
    """
    for entry in R.RESTORATIONS:
        assert 'href="#' not in entry.tail, entry.filename


def test_no_restored_tail_reintroduces_a_retired_brand():
    """The site publishes as ICU Notebook; the pre-rename names must not come back."""
    for entry in R.RESTORATIONS:
        assert "ARIA Capital Holdings" not in entry.tail, entry.filename
        assert "Money Psychology" not in entry.tail, entry.filename


def test_every_link_in_a_restored_tail_resolves():
    for entry in R.RESTORATIONS:
        for href in re.findall(r'href="([^"]+\.html)"', entry.tail):
            if href.startswith(("http://", "https://", "//")):
                continue
            assert os.path.exists(os.path.join(HERE, href)), f"{entry.filename} -> {href}"


# --- corpus-level invariant --------------------------------------------------


def test_no_restored_page_still_ends_mid_word():
    """
    Each of these pages used to stop mid-sentence with the injected trailing blocks pasted
    straight onto the cut. The restored text has to actually close the sentence.
    """
    for entry in R.RESTORATIONS:
        with open(os.path.join(HERE, entry.filename), encoding="utf-8") as fh:
            html = fh.read()
        at = html.index(entry.anchor) + len(entry.anchor) + len(entry.tail)
        following = html[at:at + 400].lstrip()
        assert following.startswith(("<", "")), entry.filename
        assert entry.tail.rstrip().endswith(">"), entry.filename
