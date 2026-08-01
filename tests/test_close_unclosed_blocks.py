"""
Tests for close_unclosed_blocks.py.

The repair inserts closing tags into 141 live articles, so the thing worth proving is not
that it fires — it is that it fires in the RIGHT PLACE and refuses everywhere else. Three
failure modes matter: closing a leaf block over content that belongs after it, closing a
wrapper inside the article instead of before the trailing blocks, and touching a file that
was already fine.

The corpus-level test at the bottom is the one that guards the invariant going forward.
"""
import os
import re

import close_unclosed_blocks as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEAD = "<html><head></head><body>\n"
TRAILING = '<div id="related-articles">r</div>\n</body>\n</html>\n'


def page(middle: str) -> str:
    return HEAD + middle + TRAILING


# --- leaf blocks (callout / warning / hero-note) -----------------------------


def test_unclosed_leaf_is_closed_after_its_content_line():
    out, _ = C.repair(page('<div class="callout">\n<strong>x</strong> y</p>\n\n<h2>next</h2>\n'))
    assert out is not None
    assert '<strong>x</strong> y</p>\n</div>\n' in out
    assert out.index("</div>") < out.index("<h2>next</h2>")


def test_leaf_already_closed_on_its_own_line_is_left_alone():
    assert C.repair(page('<div class="callout">\n<strong>x</strong></p>\n</div>\n')) == (None, [])


def test_leaf_already_closed_inline_is_left_alone():
    assert C.repair(page('<div class="callout">\n<strong>x</strong></p></div>\n')) == (None, [])


def test_a_two_line_leaf_closes_after_the_second_line():
    """parkland-formula-burn-resuscitation-2026.html: line one ends <br>, not </p>."""
    out, _ = C.repair(
        page('<div class="callout">\n<strong>a</strong><br>\nb</p>\n<p>sibling</p>\n')
    )
    assert out is not None
    assert "b</p>\n</div>\n<p>sibling</p>" in out


def test_a_leaf_running_past_two_lines_is_reported_not_guessed_at():
    out, notes = C.repair(
        page('<div class="callout">\n<strong>a</strong>\nb\nc\nd</p>\n<p>sibling</p>\n')
    )
    assert out is None
    assert any("runs past" in n for n in notes)


def test_each_of_the_three_leaf_classes_is_recognised():
    for cls in ("callout", "warning", "hero-note"):
        out, _ = C.repair(page(f'<div class="{cls}">\n<strong>x</strong></p>\n\n<h2>h</h2>\n'))
        assert out is not None, cls


# --- wrappers (container / main / article / list) ----------------------------


def test_unclosed_container_closes_before_the_trailing_blocks():
    out, _ = C.repair(page('<div class="container">\n<p>body</p>\n'))
    assert out is not None
    assert out.index("</div>") < out.index('<div id="related-articles"')


def test_unclosed_main_closes_after_its_children_not_before_them():
    """<main> wraps the container, so </main> belongs AFTER </div>, not before it."""
    out, _ = C.repair(page('<main>\n<div class="container">\n<p>body</p>\n</div>\n'))
    assert out is not None
    assert out.index("</div>") < out.index("</main>") < out.index('<div id="related-articles"')


def test_an_unclosed_list_closes_before_its_parents_closing_tag():
    """roth-ira-for-nurses-complete-guide.html: an <ol> the enclosing </div> was closing."""
    out, _ = C.repair(page("<div>\n<ol>\n<li>a</li>\n<li>b</li>\n</div>\n"))
    assert out is not None
    assert out.index("</ol>") < out.index("</div>")


def test_a_well_formed_page_is_untouched():
    assert C.repair(page('<main>\n<div class="container">\n<p>body</p>\n</div>\n</main>\n')) == (None, [])


# --- idempotency and the write-time guard ------------------------------------


def test_repair_is_idempotent():
    once, _ = C.repair(page('<div class="container">\n<div class="callout">\n<strong>x</strong></p>\n\n<h2>h</h2>\n'))
    assert once is not None
    assert C.repair(once) == (None, [])


def test_structural_problems_is_silent_on_a_well_formed_page():
    assert C.structural_problems(page('<main>\n<p>body</p>\n</main>\n')) == []


def test_structural_problems_catches_a_trailing_block_trapped_inside_a_wrapper():
    trapped = HEAD + '<div class="container">\n' + TRAILING
    assert any("depth" in p for p in C.structural_problems(trapped))


def test_structural_problems_catches_mis_nesting_that_still_counts_even():
    """</article> closing a <div> balances the counts and is still wrong."""
    problems = C.structural_problems(page("<div>\n<article>\n<p>x</p>\n</div>\n</article>\n"))
    assert any("closes" in p for p in problems)


# --- corpus-level invariant --------------------------------------------------


def test_every_article_is_structurally_sound():
    """
    The point of the script. 141 articles were shipping unclosed <div>/<main>/<article>/
    <ol> tags, which nested the footer, cookie banner and related-articles card inside the
    article body. If a future bulk edit reintroduces one, this fails rather than shipping it.
    """
    broken = {}
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
            problems = C.structural_problems(fh.read())
        if problems:
            broken[name] = problems
    assert broken == {}


def test_no_article_leaves_a_block_element_unclosed():
    unbalanced = {}
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(HERE, name), encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        deltas = {t: C.tag_balance(html, t) for t in C.CONTAINER_TAGS if C.tag_balance(html, t)}
        if deltas:
            unbalanced[name] = deltas
    assert unbalanced == {}
