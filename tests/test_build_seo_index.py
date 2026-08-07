"""
Guards on the footer template build_seo_index.py stamps onto index.html.

Added 2026-08-07 after finding two defects sitting in it, neither of them live yet — which
is the point. This is a GENERATOR: nothing it emits is wrong until someone runs it, and then
it is wrong on the homepage. The identical shape already bit this repo once, when
inject_shared_css.py held a dead store handle in the template it stamps onto ~1,400 pages.

  1. The footer linked to https://gumroad.com/l/aria-capital — measured HTTP 404. The live
     store is icunotebook.gumroad.com, already correct in the GUMROAD_URL constant twelve
     lines up. Two store URLs in one file, one of them dead.
  2. It read "Guides for nurses, by a nurse-investor" — an authorship credential claim, which
     standing priority 2 forbids (publish as the entity, never as a named individual or a
     claimed credential). Same family as the "I'm Carlos, an ICU/PCU nurse" store bio and the
     licensed-RN review claim, both of which had to be swept afterwards.

Test the emitted template, not the constant, because the bug was that the two disagreed.
"""
import re

import build_seo_index as B

FOOTER_RE = re.compile(r"<footer>.*?</footer>", re.S)


def _footer():
    """The footer as it would actually be written, with f-string substitution applied."""
    html = B.build_index_html([]) if hasattr(B, "build_index_html") else None
    if html is None:                      # fall back to the module source template
        src = open(B.__file__, encoding="utf-8").read()
        m = FOOTER_RE.search(src)
        assert m, "no <footer> template found in build_seo_index.py"
        return m.group(0).replace("{GUMROAD_URL}", B.GUMROAD_URL)
    m = FOOTER_RE.search(html)
    assert m, "generated index.html has no footer"
    return m.group(0)


def test_footer_points_at_the_live_store_not_a_second_hardcoded_url():
    footer = _footer()
    assert B.GUMROAD_URL in footer, "footer does not use the GUMROAD_URL constant"
    assert "gumroad.com/l/aria-capital" not in footer, (
        "footer carries the dead store URL (measured HTTP 404 on 2026-08-07)")


def test_only_one_gumroad_url_exists_in_the_module():
    # The defect was two URLs disagreeing, not either one alone.
    src = open(B.__file__, encoding="utf-8").read()
    urls = set(re.findall(r"https?://[a-z0-9.\-]*gumroad\.com[^\"'\s)]*", src))
    assert urls <= {B.GUMROAD_URL}, f"more than one Gumroad URL in the module: {urls}"


def test_footer_makes_no_authorship_or_credential_claim():
    footer = _footer().lower()
    for phrase in ("nurse-investor", "by a nurse", "licensed", "registered nurse",
                   "reviewed by", "written by a"):
        assert phrase not in footer, f"footer claims authorship/credential: {phrase!r}"


def test_footer_still_names_the_publishing_entity():
    # Standing priority 2 requires the entity to be named — removing the personal claim
    # must not remove attribution altogether.
    assert "ARIA Capital Holdings LLC" in _footer()
