#!/usr/bin/env python3
"""
restore_newsletter_blocks.py — put back the 171 email-capture forms that the
truncation repair discarded.

WHY THIS EXISTS
fix_truncated_articles.py excised damaged trailing blocks rather than repairing them.
That was right for promo boilerplate and wrong for the newsletter block: it is a beehiiv
signup form, i.e. the site's email list, and it went from 1,359 pages to 1,188.

A later analysis established that the damaged fragments are recoverable EXACTLY, not
approximately. Every structurally complete newsletter block in the 1,139 healthy files
reduces to two templates, and each of the 171 damaged fragments is a byte-exact prefix of
one of them once the heading and subhead are read from the file itself.

HOW A TEMPLATE IS CHOSEN
Never from the lead comment — that is not a function of the content. The heading and
subhead are read from lines 2 and 3 of the surviving fragment and looked up in a whitelist
of the three observed pairs. Then the rendered template must satisfy
    template.startswith(fragment.rstrip())
Any failure refuses the file and reports it, rather than emitting a guess.

NL_ARIA's ending cannot be derived from the working tree — "Get the ARIA Finance Weekly"
appears in zero healthy files. It is settled from git: all 25 pre-truncation ancestors end
with the No-spam paragraph and </div> and NO end comment, unanimously.

The fragments are read from the pre-repair commit, since the repair already removed them.

IDEMPOTENT: a page that already has a structurally complete newsletter block is skipped.

USAGE
    python3 restore_newsletter_blocks.py --dry-run
    python3 restore_newsletter_blocks.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

from check_site_integrity import IntegrityError, html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# The commit immediately before fix_truncated_articles.py ran.
PRE_REPAIR = "7a9241c"

NL_START = '<div style="margin:40px auto;max-width:520px;'
HP = '  <p style="margin:0 0 6px;font-size:18px;font-weight:bold;color:#1a202c;">'
SP = '  <p style="margin:0 0 18px;font-size:14px;color:#4a5568;">'

_HEAD = (
    '<div style="margin:40px auto;max-width:520px;padding:28px 24px;background:#f8f9fa;'
    'border:1px solid #e2e8f0;border-radius:8px;font-family:Georgia,serif;text-align:center;">\n'
    f"{HP}{{H}}</p>\n"
    f"{SP}{{S}}</p>\n"
)

# 2026-09-02 — THE FORM IS GONE ON PURPOSE. It POSTed to
# embeds.beehiiv.com/pub_5335792c-.../subscribe, which renders "Not found" in a
# real browser, byte-identical to a publication id that cannot exist, and had
# been doing so on 1,359 live pages for at least 25 days. Measured with controls:
# the same browser renders a working Email field and Subscribe button at
# icu-notebook.beehiiv.com/subscribe, so "Not found" was a real answer and not a
# blocked vantage. The bare-uuid variant was tested too and also 404s.
# A LINK, not a repointed form: that subscribe page is a page, not a form
# endpoint, so a POST would subscribe nobody, and a GET form would put a
# visitor's email address into a URL query string where referrers and logs keep
# it. beehiiv's own form does the capture instead.
# DO NOT restore a <form> here without loading its target in a browser first.
# A 200 from curl is what hid this for 25 days: the endpoint returned 200 and a
# React shell that said "You need to enable JavaScript", and every status-code
# check passed while every visitor saw "Not found".
_CTA = (
    '  <a href="https://icu-notebook.beehiiv.com/subscribe" target="_blank" rel="noopener" '
    'style="display:inline-block;padding:12px 20px;background:#2563eb;color:#fff;border:none;'
    'border-radius:6px;font-size:15px;font-weight:bold;text-decoration:none;cursor:pointer;">'
    "Yes, send it free</a>\n"
)
_TAIL = (
    '  <p style="margin:12px 0 0;font-size:12px;color:#718096;">No spam. Unsubscribe any time.</p>\n'
    "</div>"
)

NL_ICU = _HEAD + _CTA + _TAIL + "\n<!-- /email-capture -->"

NL_ARIA = _HEAD + _CTA + _TAIL

# The only (heading, subhead) pairs observed anywhere in the corpus or its history.
TRIPLES = {
    ("Get the ICU Notebook",
     "Free investing strategies built for nurses. One email per week, no fluff."): NL_ICU,
    ("Get The ICU Notebook Newsletter",
     "Clinical tools and career insights for ICU nurses. One email per week, no fluff."): NL_ICU,
    ("Get the ARIA Finance Weekly",
     "Practical money strategies, one email per week. No fluff."): NL_ARIA,
}


def git_show(ref: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", HERE, "show", f"{ref}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def block_complete(text: str) -> bool:
    """True if a structurally complete newsletter div is present."""
    start = text.find(NL_START)
    if start == -1:
        return False
    depth = 0
    for m in re.finditer(r"<div\b|</div>", text[start:]):
        depth += 1 if m.group(0) != "</div>" else -1
        if depth == 0:
            return True
    return False


def render(fragment: str) -> str | None:
    """Complete a damaged fragment into its canonical block, or None if it cannot be settled."""
    lines = fragment.split("\n")
    if len(lines) < 3:
        return None
    head, sub = lines[1], lines[2]
    if not (head.startswith(HP) and head.rstrip().endswith("</p>")):
        return None
    if not (sub.startswith(SP) and sub.rstrip().endswith("</p>")):
        return None

    h = head[len(HP):].rstrip()[:-len("</p>")]
    s = sub[len(SP):].rstrip()[:-len("</p>")]

    template = TRIPLES.get((h, s))
    if template is None:
        return None

    rendered = template.replace("{H}", h).replace("{S}", s)
    # The fragment must be a byte-exact prefix; otherwise we would be inventing markup.
    if not rendered.startswith(fragment.rstrip()):
        return None
    return rendered


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    restored = skipped = refused = unsettled = 0
    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        if block_complete(text):
            skipped += 1
            continue

        old = git_show(PRE_REPAIR, name)
        if old is None or NL_START not in old:
            continue  # this page never had a newsletter block

        fragment = old[old.index(NL_START):]
        # The fragment ran to end-of-file in the truncated original.
        rendered = render(fragment)
        if rendered is None:
            unsettled += 1
            print(f"  UNSETTLED {name}: fragment does not match a known template")
            continue

        at = text.rfind("</body>")
        if at == -1:
            unsettled += 1
            print(f"  UNSETTLED {name}: no </body> to insert before")
            continue
        new_text = text[:at] + rendered + "\n" + text[at:]

        regressions = severity_regressions(html_severity(text), html_severity(new_text))
        if regressions:
            refused += 1
            print(f"  REFUSED {name}: would regress {regressions}")
            continue

        restored += 1
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            restored -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}newsletter forms restored: {restored} | "
          f"already complete: {skipped} | unsettled: {unsettled} | refused: {refused}")
    return 1 if (refused or unsettled) else 0


if __name__ == "__main__":
    raise SystemExit(main())
