#!/usr/bin/env python3
"""
fix_truncated_articles.py — close the 322 articles that were cut off mid-write.

WHY THIS EXISTS
These are the last survivors of the truncation-bug family. Each file was cut while a
writer was appending its trailing blocks, so the document simply stops: no </body>, no
</html>, and whatever block the cut landed in is left half-written.

The article's own content is intact in every case. What is lost is a fragment of a
generated promo/disclaimer block, and the closing tags.

APPROACH
Trailing blocks are machine-generated and delimited, so each can be validated independently
rather than guessed at:

    gumroad     <!-- gumroad-cta              ...  <!-- /gumroad-cta -->
    related     <div id="related-articles"    ...  its matched </div>
    affiliate   <!-- AFFILIATE-CTA            ...  <!-- /AFFILIATE-CTA
    footer      <footer                       ...  </footer>
    cookie      <!-- COOKIE CONSENT BANNER    ...  <!-- END COOKIE BANNER -->
    newsletter  <div style="margin:40px auto  ...  <!-- /email-capture -->

A damaged block in the MIDDLE of the document is repaired (only the newsletter occurs
this way, and only where the fragment ends at </form>, so the canonical tail can be
re-attached). A damaged block at the END is excised — there is nothing after it to
preserve and its content is boilerplate.

Then the article body is closed. The critical subtlety, which cost the analysis several
wrong turns, is that only the INNERMOST unclosed <div> may be discarded — and only when it
is a short, non-wrapper leaf, i.e. the fragment the cut actually landed in. Outer divs held
complete content, so they are CLOSED, never discarded. Cascading the excision outward was
measured to destroy four complete sibling cards in about.html.

MEASURED over all 322 files: 319 reach a fully clean severity of
{unterminated: False, div_delta: 0, tag_errors: 0, unterminated_attr: 0}.
Zero regressions on any metric on any file. Zero of the 1,139 healthy files are touched.
The most article text lost in any single file is 450 bytes, and every discarded byte is a
mid-word-truncated promo fragment.

Three files are deliberately left for separate handling; see RESIDUALS at the bottom.

IDEMPOTENT.

USAGE
    python3 fix_truncated_articles.py --dry-run
    python3 fix_truncated_articles.py
"""
from __future__ import annotations

import collections
import os
import re
import sys

from check_site_integrity import IntegrityError, html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# (name, start marker, terminator). A None terminator means "the div that matches it".
BLOCKS = [
    ("gumroad", "<!-- gumroad-cta", "<!-- /gumroad-cta -->"),
    ("related", '<div id="related-articles"', None),
    # The injector emits "<!-- /AFFILIATE-CTA:<id> -->", so match the prefix, not a
    # closing "-->" that never appears in that exact form.
    ("affiliate", "<!-- AFFILIATE-CTA", "<!-- /AFFILIATE-CTA"),
    ("footer", "<footer", "</footer>"),
    ("cookie", "<!-- COOKIE CONSENT BANNER", "<!-- END COOKIE BANNER -->"),
    ("newsletter", '<div style="margin:40px auto;max-width:520px;', "<!-- /email-capture -->"),
]

# The newsletter block is preceded by a lead comment that belongs to it.
LEAD = re.compile(r"<!--[^>]*?email capture[^>]*?-->\s*$", re.I)

NEWSLETTER_TAIL = (
    '\n  <p style="margin:12px 0 0;font-size:12px;color:#718096;">'
    "No spam. Unsubscribe any time.</p>\n</div>\n<!-- /email-capture -->"
)

# A <div> carrying one of these classes wraps real content; never discard one.
WRAPPER_CLASSES = {"container", "wrapper", "site-wrapper", "page-wrapper",
                   "main", "content", "article-body"}

# Largest fragment we are willing to discard. Observed leaves top out at 447 bytes and the
# smallest observed wrapper is 10,520 — so this sits with ~4.5x headroom on both sides.
LEAF_MAX = 2048

DIV_TOKEN = re.compile(r"<div\b|</div>")
PARTIAL_TAG = re.compile(r"<[^>]*$")


def occurrences(text: str) -> list[list]:
    """Every trailing-block occurrence as [start, name, terminator], in document order."""
    found = []
    for name, start_marker, terminator in BLOCKS:
        i = 0
        while True:
            p = text.find(start_marker, i)
            if p == -1:
                break
            start = p
            if name == "newsletter":
                m = LEAD.search(text, max(0, p - 160), p)
                if m:
                    start = m.start()
            found.append([start, name, terminator])
            i = p + 1
    found.sort(key=lambda x: x[0])
    return found


def matched_div_end(text: str, start: int) -> int | None:
    """End offset of the </div> matching the <div> at `start`, or None if never closed."""
    depth = 0
    for m in DIV_TOKEN.finditer(text, start):
        if m.group(0) == "</div>":
            depth -= 1
            if depth == 0:
                return m.end()
        else:
            depth += 1
    return None


def block_intact(text: str, start: int, terminator: str | None, limit: int) -> bool:
    """True if the block starting at `start` closes before `limit`."""
    if terminator is None:
        end = matched_div_end(text, start)
        return end is not None and end <= limit
    at = text.find(terminator, start)
    return at != -1 and at < limit


def unclosed_divs(text: str) -> list[int]:
    """Start offsets of every <div> never closed, outermost first."""
    stack: list[int] = []
    for m in DIV_TOKEN.finditer(text):
        if m.group(0) == "</div>":
            if stack:
                stack.pop()
        else:
            stack.append(m.start())
    return stack


def trim_partial_tag(text: str) -> str:
    """
    Drop a half-written tag at the end. MANDATORY: an unterminated tag or quoted attribute
    would otherwise swallow every closing tag we append.
    """
    m = PARTIAL_TAG.search(text)
    return text[:m.start()] if m else text


def first_class(text: str, start: int) -> str:
    gt = text.find(">", start)
    tag = text[start:gt + 1] if gt != -1 else text[start:start + 200]
    m = re.search(r'class="([^"]*)"', tag)
    if not m:
        return ""
    parts = m.group(1).split()
    return parts[0] if parts else ""


def repair(data: bytes) -> bytes | None:
    """Repair a truncated article. Returns None if the file needs no work."""
    # Some files were padded with NUL bytes rather than truncated. Strip and re-check:
    # if the document is actually complete underneath, only the padding was the problem.
    if b"\x00" in data:
        stripped = data.rstrip(b"\x00 \t\r\n")
        if stripped.endswith(b"</html>"):
            return stripped + b"\n"
        data = stripped

    text = data.decode("utf-8", "replace")
    if text.rstrip().endswith("</html>"):
        return None

    occ = occurrences(text)
    if not occ:
        body, tail = text, ""
    else:
        # Repair a damaged block in the MIDDLE of the document. Only the newsletter occurs
        # this way; require the fragment to end at </form> so the canonical tail attaches to
        # a known point rather than being guessed onto arbitrary text.
        changed = True
        while changed:
            changed = False
            occ = occurrences(text)
            for i, (pos, name, terminator) in enumerate(occ):
                if i == len(occ) - 1:
                    continue
                nxt = occ[i + 1][0]
                if name == "newsletter" and not block_intact(text, pos, terminator, nxt):
                    fragment = text[pos:nxt].rstrip()
                    if fragment.endswith("</form>"):
                        text = text[:pos] + fragment + NEWSLETTER_TAIL + "\n" + text[nxt:]
                        changed = True
                        break

        # Excise a damaged block at the END. Nothing follows it, and its content is
        # generated boilerplate rather than article text.
        occ = occurrences(text)
        pos, _, terminator = occ[-1]
        if not block_intact(text, pos, terminator, len(text)):
            text = text[:pos]

        occ = occurrences(text)
        body_end = occ[0][0] if occ else len(text)
        body, tail = text[:body_end], text[body_end:]

    body = trim_partial_tag(body).rstrip()

    # Discard ONLY the innermost unclosed div, and only if it is a short non-wrapper leaf:
    # that is the fragment the cut landed in. Everything outside it holds complete content
    # and is closed rather than discarded.
    stack = unclosed_divs(body)
    if stack:
        innermost = stack[-1]
        if (first_class(body, innermost) not in WRAPPER_CLASSES
                and (len(body) - innermost) <= LEAF_MAX):
            body = trim_partial_tag(body[:innermost]).rstrip()

    body += "\n</div>" * len(unclosed_divs(body))

    out = body + "\n" + tail.rstrip()
    if out.count("<script") > out.count("</script>"):
        out = out.rstrip() + "\n</script>"  # two calculator pages are cut inside JS
    return (out.rstrip() + "\n</body>\n</html>\n").encode("utf-8")


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    repaired = refused = skipped = 0
    after_states: collections.Counter = collections.Counter()
    residuals: list[str] = []

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, "rb") as fh:
            data = fh.read()

        text = data.decode("utf-8", "replace")
        if text.rstrip().endswith("</html>") and b"\x00" not in data:
            continue

        out = repair(data)
        if out is None:
            skipped += 1
            continue

        new_text = out.decode("utf-8", "replace")
        before, after = html_severity(text), html_severity(new_text)

        regressions = severity_regressions(before, after)
        if regressions:
            refused += 1
            print(f"  REFUSED {name}: would regress {regressions}")
            continue

        state = (after["unterminated"], after["div_delta"],
                 after["tag_errors"], after["unterminated_attr"])
        after_states[state] += 1
        if any(state):
            residuals.append(f"{name} -> {dict(zip(('unterminated','div_delta','tag_errors','unterm_attr'), state))}")

        repaired += 1
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            repaired -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}repaired: {repaired} | refused: {refused} | already clean: {skipped}")
    print("  resulting severity (unterminated, div_delta, tag_errors, unterm_attr):")
    for state, n in sorted(after_states.items(), key=lambda x: -x[1]):
        print(f"    {state}  x{n}{'   <- fully clean' if not any(state) else ''}")
    if residuals:
        print("\n  RESIDUALS (left for separate handling):")
        for r in residuals:
            print("   -", r)
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
