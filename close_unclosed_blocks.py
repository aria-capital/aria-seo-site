#!/usr/bin/env python3
"""
close_unclosed_blocks.py — close the block elements that 141 articles never close.

WHY THIS EXISTS
This is the last of the corpus damage. Unlike the truncation family, most of it was never
cut off mid-write: the files end with a clean </body></html>, and the damage is present in
the FIRST commit that introduced them, so git history holds no better copy. The generator
that wrote these articles simply omitted closing tags.

The effect is not cosmetic. When `<div class="container">` never closes, the browser nests
the footer, the cookie banner, the newsletter form and the related-articles card inside the
article body instead of after it — they inherit the article's width and styling. When a
`callout` never closes, every heading and paragraph after it renders inside the callout box
for the rest of the page. When `<main>` never closes, the same happens one level up.

WHAT IS BROKEN, MEASURED
    236  callout / warning / hero-note blocks opened on their own line and never closed
    111  `.container` wrappers never closed before the trailing injected blocks
     14  <main> / <article> / <ol> wrappers never closed

APPROACH — two rules, both derived from the 1,334 healthy files, then verified per file
rather than trusted:

1. A `<div class="callout|warning|hero-note">` on a line of its own is a leaf block whose
   content is the run of lines up to the next block-level sibling (a blank line, or a line
   opening <h2>/<p>/<div>/<table>/...). In the healthy corpus that rule predicts the real
   position of the closing </div> for 2,347 of 2,355 blocks; the 8 misses are all blocks
   whose content runs longer than two lines, so the rule refuses to fire past two and
   reports instead of guessing.

2. Any other unclosed container closes at the first of: the closing tag that would
   otherwise swallow it (an ancestor's), or the first trailing injected block. In the
   healthy corpus the trailing blocks sit at div depth 0 in every single file — 1,333 of
   1,333 — which is the invariant this rule restores.

Neither rule is trusted on its own. After applying them the file must pass
structural_problems(): every block tag balanced, no closing tag without an opener, and the
trailing blocks back at depth 0. If it does not, the file is left untouched and reported.
That check is what makes the repair safe — a rule that misfires cannot ship, because a
misfire cannot produce a well-formed document.

No article text is added, removed or reordered — the only bytes written are closing tags.
(Text that a truncated write actually deleted is a different repair; see
restore_truncated_blocks.py, which runs first.)

IDEMPOTENT — a closed block is not an unclosed one, so a second run finds nothing.

USAGE
    python3 close_unclosed_blocks.py --dry-run
    python3 close_unclosed_blocks.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# A leaf block opened on a line of its own. These three classes are the only ones the
# generator emits this way, and they never wrap other blocks in the healthy corpus.
LEAF_OPEN = re.compile(r'^<div class="(?:callout|warning|hero-note)">\s*$')

# A line that starts a new block-level sibling, i.e. the leaf's content has ended.
# The leading `</` case matters: it catches a leaf that IS already closed.
SIBLING = re.compile(
    r"^\s*(?:$|</|<h[1-6]\b|<p\b|<div\b|<table\b|<ul\b|<ol\b|<blockquote\b|<section\b|<footer\b|<!--)"
)

# Longest content run this script will close over. Healthy leaves are 1 line (2,348 of
# 2,355) or 2 (parkland-formula-burn-resuscitation-2026.html, whose first line ends <br>).
# Anything longer is a block whose extent this rule cannot establish, so it is left alone.
MAX_LEAF_LINES = 2

# Elements that must nest. <p>, <li> and <td> are deliberately absent: the corpus closes
# them loosely (a stray </p> with no <p> is the house style in every callout), so counting
# them would report damage that is not there.
CONTAINER_TAGS = (
    "div", "main", "article", "section", "aside", "nav", "header", "footer",
    "ol", "ul", "table", "form", "figure", "blockquote",
)
CONTAINER_TOKEN = re.compile(
    r"</?(?:%s)\b[^>]*>|<!-- COOKIE CONSENT BANNER|</body>" % "|".join(CONTAINER_TAGS)
)
NESTING_TOKEN = re.compile(r"</?(%s)\b[^>]*>" % "|".join(CONTAINER_TAGS))

# The run of generated blocks appended after the article. A wrapper closes before these.
TRAILING_MARKERS = (
    '<div class="footer">',
    '<div style="text-align:center;padding:4px 0;font-size:0.8em;',
    '<div id="related-articles"',
    "<!-- COOKIE CONSENT BANNER",
    '<div id="cookie-banner"',
    "</body>",
)
# NOTE: `<div class="cta-box">` is deliberately NOT a trailing marker. It follows the
# container's close in exactly one healthy file, but it is in-article content in the rest
# — night-shift-nurse-budget-money-strategy.html ends with an in-article cta-box, and
# treating it as trailing put </article> in the middle of the page.

# Trailing blocks that must sit OUTSIDE the article wrapper. Verified at div depth 0 in
# all 1,333 healthy articles, with no exceptions.
DEPTH_ZERO_MARKERS = (
    '<div class="footer">',
    '<div id="related-articles"',
    "<!-- COOKIE CONSENT BANNER",
    "</body>",
)
DEPTH_TOKEN = re.compile(r"<div\b[^>]*>|</div>|<!-- COOKIE CONSENT BANNER|</body>")


def tag_balance(html: str, tag: str) -> int:
    """Open tags minus closing ones. >0 means something is never closed."""
    return len(re.findall(r"<%s\b" % tag, html)) - html.count("</%s>" % tag)


def div_delta(html: str) -> int:
    return tag_balance(html, "div")


def unclosed_openers(html: str, tag: str) -> list[int]:
    """Offsets of every <tag> left open at end of document."""
    stack: list[int] = []
    for m in re.finditer(r"<%s\b[^>]*>|</%s>" % (tag, tag), html):
        if m.group(0).startswith("</"):
            if stack:
                stack.pop()
        else:
            stack.append(m.start())
    return stack


def close_leaf_blocks(lines: list[str]) -> tuple[list[str], list[str]]:
    """
    Close every callout/warning/hero-note opened on its own line and left open.

    Works purely locally — no document-wide stack. A stack mis-attributes here: an
    unclosed leaf swallows its parent's </div>, so the parent gets blamed for the child's
    missing tag. Asking "does the line after this opener end the block, and is there a
    </div> there?" is the question that actually has a reliable answer.
    """
    out: list[str] = []
    unresolved: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if not LEAF_OPEN.match(lines[i]):
            i += 1
            continue

        # Content is the run of lines before the next block-level sibling.
        run_end = i
        while run_end + 1 < len(lines) and run_end - i < MAX_LEAF_LINES:
            if SIBLING.match(lines[run_end + 1]):
                break
            run_end += 1

        if run_end == i:
            unresolved.append(f"line {i + 1}: leaf block has no content line")
            i += 1
            continue
        if run_end - i >= MAX_LEAF_LINES and not SIBLING.match(lines[min(run_end + 1, len(lines) - 1)]):
            unresolved.append(f"line {i + 1}: leaf block runs past {MAX_LEAF_LINES} lines")
            i += 1
            continue

        content = lines[i + 1:run_end + 1]
        already_closed = content[-1].rstrip().endswith("</div>") or (
            run_end + 1 < len(lines) and lines[run_end + 1].strip() == "</div>"
        )
        out.extend(content)
        if not already_closed:
            out.append("</div>")
        i = run_end + 1
    return out, unresolved


def insertion_point(html: str, tag: str, opener: int) -> int | None:
    """
    Where the missing `</tag>` for the opener at `opener` belongs, or None if the rule
    cannot establish a position.

    Two outcomes, both taken from how the healthy corpus is shaped:
      - Some ANCESTOR's closing tag comes first. That tag is currently swallowing this
        element, so the close goes immediately before it. (`roth-ira-...`: an <ol> left
        open inside a <div>, and the div's </div> is what ends up closing the list.)
      - Nothing closes it, and the first trailing injected block arrives while it is still
        open. The close goes immediately before that block. (Every `.container`, and every
        <main>/<article> here.)
    """
    depth = 0
    for m in CONTAINER_TOKEN.finditer(html, opener):
        pos = m.start()
        if pos > opener and any(html.startswith(mk, pos) for mk in TRAILING_MARKERS):
            return html.rfind("\n", 0, pos) + 1
        token = m.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                # Already closed by its own tag — then it was not unclosed after all.
                if token == "</%s>" % tag:
                    return None
                return html.rfind("\n", 0, pos) + 1
        elif token.startswith("<"):
            depth += 1
    return None


def close_wrappers(html: str) -> tuple[str, list[str]]:
    """Close every still-unclosed container, innermost first, one at a time."""
    notes: list[str] = []
    for _ in range(32):  # bounded: no real article nests anywhere near this deep
        open_now = [
            (pos, tag)
            for tag in CONTAINER_TAGS
            for pos in unclosed_openers(html, tag)
        ]
        if not open_now:
            return html, notes
        pos, tag = max(open_now)  # innermost/latest first, so outer closes land after it
        at = insertion_point(html, tag, pos)
        if at is None:
            notes.append(f"<{tag}> at offset {pos}: no position for its closing tag")
            return html, notes
        html = html[:at] + "</%s>\n" % tag + html[at:]
    notes.append("gave up after 32 closing tags — something is looping")
    return html, notes


def repair(html: str) -> tuple[str | None, list[str]]:
    """
    (repaired document, notes). None means nothing was done — either the file was already
    well-formed, or the rules could not bring it to a well-formed state and it is being
    left alone deliberately.
    """
    if not any(tag_balance(html, t) > 0 for t in CONTAINER_TAGS):
        return None, []

    lines, notes = close_leaf_blocks(html.split("\n"))
    if notes:
        # Rule 1 could not establish where a leaf ends. Rule 2 would then "close" it at the
        # trailing blocks, which is the worst possible answer — it would swallow the rest of
        # the article into a callout box. Refuse the whole file instead.
        return None, notes

    out, more = close_wrappers("\n".join(lines))
    notes += more

    if out == html:
        return None, notes
    return out, notes


def structural_problems(html: str) -> list[str]:
    """
    Everything that must hold before a repaired buffer is allowed to be written.

    A balanced tag count is necessary but NOT sufficient — a document can reach a delta of
    zero with its nesting still wrong, if a rule closed one block in the wrong place and
    another block absorbed the difference. So the depth is walked, and the trailing
    injected blocks are required to sit at depth 0. That is the property this repair is
    actually for: the footer, cookie banner, related-articles card and </body> belong AFTER
    the article wrapper, not inside it. All four hold at depth 0 in every one of the 1,333
    healthy articles, with no exceptions.
    """
    problems: list[str] = []
    if not html.rstrip().endswith("</html>"):
        problems.append("does not end with </html>")
    for tag in ("</head>", "</body>", "</html>"):
        n = html.count(tag)
        if n != 1:
            problems.append(f"expected exactly 1 '{tag}', found {n}")
    # Proper nesting, not just matching counts: </article> must close the <article> that is
    # actually open, not one that a stray </div> already ended. Every one of the 1,461
    # articles satisfies this once repaired, so it is safe to require.
    stack: list[str] = []
    for m in NESTING_TOKEN.finditer(html):
        token = m.group(0)
        name = m.group(1)
        if token.startswith("</"):
            if not stack:
                problems.append(f"</{name}> with nothing open")
                break
            if stack[-1] != name:
                problems.append(f"</{name}> closes <{stack[-1]}>")
                break
            stack.pop()
        elif not token.endswith("/>"):
            stack.append(name)
    if stack:
        problems.append("never closed: " + ", ".join(f"<{t}>" for t in stack))

    depth = 0
    floor = 0
    at: dict[str, int] = {}
    for m in DEPTH_TOKEN.finditer(html):
        token = m.group(0)
        if token == "</div>":
            depth -= 1
            floor = min(floor, depth)
            continue
        marker = next((k for k in DEPTH_ZERO_MARKERS if token.startswith(k)), None)
        if marker is not None:
            at.setdefault(marker, depth)   # depth BEFORE this div counts itself
        if token.startswith("<div"):
            depth += 1

    if floor < 0:
        problems.append(f"a </div> closes a div that was never opened (depth reached {floor})")
    for marker, d in sorted(at.items()):
        if d != 0:
            problems.append(f"{marker!r} sits at div depth {d}, should be 0")
    return problems


def main() -> int:
    dry = "--dry-run" in sys.argv
    repaired: list[str] = []
    skipped: list[str] = []

    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".html"):
            continue
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        if not any(tag_balance(before, t) > 0 for t in CONTAINER_TAGS):
            continue

        after, notes = repair(before)
        if after is None:
            skipped.append(f"{name}: " + ("; ".join(notes) or "no change"))
            continue

        problems = structural_problems(after)
        if problems:
            skipped.append(f"{name}: refused, still not clean — " + "; ".join(problems))
            continue
        worse = severity_regressions(html_severity(before), html_severity(after))
        if worse:
            skipped.append(f"{name}: refused, would regress — " + "; ".join(worse))
            continue

        added = sum(after.count("</%s>" % t) - before.count("</%s>" % t) for t in CONTAINER_TAGS)
        repaired.append(f"{name}: +{added} closing tag(s)" + (f"  ({'; '.join(notes)})" if notes else ""))
        if not dry:
            safe_write_html(path, after, allow_preexisting=True)

    verb = "would close" if dry else "closed"
    print(f"{verb}: {len(repaired)} file(s)")
    for line in repaired:
        print("  +", line)
    if skipped:
        print(f"skipped: {len(skipped)} file(s)")
        for line in skipped:
            print("  -", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
