#!/usr/bin/env python3
"""
fix_newsletter_form.py — replace the dead beehiiv capture form with a link to
the publication's own subscribe page, which is verified working.

MEASURED 2026-09-02, in a real browser, with controls:
  https://embeds.beehiiv.com/pub_5335792c-.../subscribe  -> "Not found"
  https://embeds.beehiiv.com/5335792c-...   (bare uuid)  -> "Not found"
  https://embeds.beehiiv.com/pub_0000...0000/subscribe   -> "Not found"  (control:
        an id that cannot exist renders IDENTICALLY to his, so his embed is
        indistinguishable from nonexistent)
  https://icu-notebook.beehiiv.com/subscribe             -> renders a real
        Email field and Subscribe button  (control: the browser CAN render a
        working beehiiv page, so "Not found" above is a real answer, not the
        vantage being blocked)

WHY A LINK AND NOT A REPOINTED FORM
  The subscribe page is a page, not a form endpoint; POSTing to it would not
  subscribe anyone. Switching to method=GET would work but would put a
  visitor's email address into a URL query string, where it leaks through
  referrer headers and server logs. A link collects nothing on his site and
  lets beehiiv's own form do the capture properly. Fewer moving parts, and
  nothing on his pages pretends to capture an address it cannot deliver.

SAFETY
  - refuses unless each touched file contains EXACTLY ONE form block
  - preserves each page's own button label
  - writes only when the content actually changed
  - --check reports without writing
  - --selftest proves it leaves a form-less page alone and refuses a malformed one
  Restore path: the repo is a clean git tree, so `git checkout -- .` reverts everything.
"""
import argparse, os, re, sys

LIVE = "https://icu-notebook.beehiiv.com/subscribe"

FORM_RE = re.compile(
    r'<form\s+action="https://embeds\.beehiiv\.com/[^"]*"[^>]*>.*?</form>',
    re.S)
LABEL_RE = re.compile(r'<button[^>]*>(.*?)</button>', re.S)

ANCHOR = ('<a href="' + LIVE + '" target="_blank" rel="noopener" '
          'style="display:inline-block;padding:12px 20px;background:#2563eb;color:#fff;'
          'border:none;border-radius:6px;font-size:15px;font-weight:bold;'
          'text-decoration:none;cursor:pointer;">%s</a>')


def convert(html):
    """Return (new_html, n_forms, label) or raise ValueError on a shape we do
    not understand. Never guesses."""
    hits = FORM_RE.findall(html)
    if len(hits) == 0:
        return html, 0, None
    if len(hits) > 1:
        raise ValueError("more than one beehiiv form in this file")
    block = hits[0]
    m = LABEL_RE.search(block)
    if not m:
        raise ValueError("no submit button label found inside the form")
    label = re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', m.group(1))).strip()
    if not label:
        raise ValueError("submit button label is empty")
    return html.replace(block, ANCHOR % label), 1, label


def walk(root, write):
    changed = skipped = untouched = 0
    problems, labels = [], {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "_site")]
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                html = open(p, encoding="utf-8").read()
            except Exception as e:
                problems.append((p, "unreadable: %s" % e)); skipped += 1; continue
            try:
                new, n, label = convert(html)
            except ValueError as e:
                problems.append((p, str(e))); skipped += 1; continue
            if n == 0:
                untouched += 1; continue
            labels[label] = labels.get(label, 0) + 1
            if new != html:
                if write:
                    open(p, "w", encoding="utf-8").write(new)
                changed += 1
    return changed, skipped, untouched, problems, labels


def selftest():
    fails = []
    good = ('<p>x</p><form action="https://embeds.beehiiv.com/pub_x/subscribe" method="POST">'
            '<input name="email"/><button type="submit">Yes, send it free</button></form><p>y</p>')
    out, n, label = convert(good)
    ok = n == 1 and label == "Yes, send it free" and LIVE in out and "embeds.beehiiv.com" not in out
    print("A converts a real block, keeps its label -> %s" % ("PASS" if ok else "FAIL"))
    if not ok: fails.append("A")

    none = "<p>a page with no newsletter form at all</p>"
    out, n, _ = convert(none)
    ok = n == 0 and out == none
    print("B leaves a form-less page byte-identical  -> %s" % ("PASS" if ok else "FAIL"))
    if not ok: fails.append("B")

    two = good + good
    try:
        convert(two); ok = False
    except ValueError:
        ok = True
    print("C refuses a file with two forms           -> %s" % ("PASS" if ok else "FAIL"))
    if not ok: fails.append("C")

    nolabel = '<form action="https://embeds.beehiiv.com/pub_x/subscribe"><input/></form>'
    try:
        convert(nolabel); ok = False
    except ValueError:
        ok = True
    print("D refuses a form with no button           -> %s" % ("PASS" if ok else "FAIL"))
    if not ok: fails.append("D")

    ph = good.replace("pub_x", "BEEHIIV_PUB_ID")
    _, n, _ = convert(ph)
    ok = n == 1
    print("E also catches the literal placeholder id -> %s" % ("PASS" if ok else "FAIL"))
    if not ok: fails.append("E")

    print()
    print("selftest: %d/5 passed%s" % (5 - len(fails), "" if not fails else "  FAILED " + ",".join(fails)))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true", help="report, write nothing")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    changed, skipped, untouched, problems, labels = walk(a.root, write=not a.check)
    print("%s: %d file(s) with a form %s, %d skipped, %d html file(s) had no form"
          % ("WOULD CHANGE" if a.check else "CHANGED", changed,
             "found" if a.check else "converted", skipped, untouched))
    print("button labels preserved:")
    for k, v in sorted(labels.items(), key=lambda x: -x[1]):
        print("  %5d  %s" % (v, k))
    if problems:
        print("\nPROBLEMS (left untouched, none were guessed at):")
        for p, why in problems[:20]:
            print("  ! %s — %s" % (p, why))
    return 0 if changed else 3


if __name__ == "__main__":
    sys.exit(main())
