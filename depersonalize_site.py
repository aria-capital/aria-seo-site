#!/usr/bin/env python3
"""
depersonalize_site.py — publish as the company, not as a named licensed nurse.

WHY THIS EXISTS
The site attached a real person's legal name AND their nursing credential to
AI-generated clinical content about drug dosing. That is the sharpest personal
exposure on the whole property, and it is not primarily a civil-liability issue:

  A Board of Nursing can act against a licensed nurse who publicly disseminates
  clinical guidance. A licence is the owner's livelihood, and a board complaint is
  a far more probable adverse event than any of the scenarios owners usually worry
  about. Bylining unreviewed drug-dosing content as "an ICU nurse" is what creates
  that specific risk.

Operating through the entity is the entire point of having formed one. This removes
the personal identifiers from the public site so the publisher of record is the LLC.

WHAT IT CHANGES
  privacy-policy.html   "operated by Carlos Trujillo, an ICU nurse building passive
                         income streams" -> the LLC. A privacy policy must identify the
                         data controller, so naming the entity is both more protective
                         AND more correct than naming the individual.
  contact.html          the personal byline -> an entity description.
  nurse-union-...html   "Arizona (Carlos's state)" -> "Arizona". A generator leaked the
                         owner's home state into published article prose.
  4 clinical pages      links to carlostrujillo.github.io/money-psychology, a personal
                         project on a personal domain -> the live site.

WHAT IT DELIBERATELY DOES NOT CHANGE
  carlos@ariacapitalholdings.com — a working mailbox on the company domain. Rewriting it
  to a role address would break contact and unsubscribe links if that mailbox does not
  exist. Flagged for the owner: switching to hello@ or support@ is a good idea once the
  alias is created.

IMPORTANT: this reduces exposure going forward. It does not retroactively unpublish
anything, and it is not a substitute for the LLC being properly maintained (separate
accounts, no commingling) or for the clinical content actually being correct.

IDEMPOTENT.

USAGE
    python3 depersonalize_site.py --dry-run
    python3 depersonalize_site.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

ENTITY = "ARIA Capital Holdings LLC"
LIVE_SITE = "https://aria-capital.github.io/aria-seo-site/"

REPLACEMENTS = [
    # Full legal name + nursing credential in the privacy policy.
    (re.compile(r"operated by Carlos Trujillo,\s*an ICU nurse building passive income streams", re.I),
     f"operated by {ENTITY}"),
    (re.compile(r"operated by Carlos Trujillo", re.I), f"operated by {ENTITY}"),

    # Personal byline claiming firsthand clinical authorship.
    (re.compile(r"ICU Notebook is written by Carlos\s*[—–-]\s*an ICU nurse building passive income "
                r"on the side while working toward CRNA school\.\s*I write from real experience, not theory\.",
                re.I),
     f"ICU Notebook is published by {ENTITY}. Articles are general educational "
     "information and are not individually reviewed by a licensed clinician."),

    # Home state leaked into article prose by a generator.
    (re.compile(r"Arizona \(Carlos(?:&#39;|')s state\)", re.I), "Arizona"),

    # Personal-domain project links inside clinical articles.
    (re.compile(r'https?://carlostrujillo\.github\.io/money-psychology/?'), LIVE_SITE),
    (re.compile(r'carlostrujillo\.github\.io/money-psychology/?'), "the ICU Notebook library"),

    # Any residual bare full name.
    (re.compile(r"\bCarlos Trujillo\b"), ENTITY),
]


def depersonalize(text: str) -> tuple[str, int]:
    total = 0
    for pattern, repl in REPLACEMENTS:
        text, n = pattern.subn(repl, text)
        total += n
    return text, total


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    changed = total = refused = 0
    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text, n = depersonalize(text)
        if not n:
            continue

        changed += 1
        total += n
        print(f"  ~ {name} ({n})")
        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            changed -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}pages changed: {changed} | "
          f"identifiers replaced: {total} | refused: {refused}")
    print(f"  publisher of record -> {ENTITY}")
    print("  NOTE: carlos@ariacapitalholdings.com left in place (working mailbox);")
    print("        switch to a role address once the alias exists.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
