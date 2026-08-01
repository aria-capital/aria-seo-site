#!/usr/bin/env python3
"""
strip_false_credentials.py — remove unsupported claims of human authorship,
professional review, and firsthand clinical experience.

WHY THIS EXISTS
The site's articles are generated, not written or reviewed by a credentialed nurse.
Commit c795a01 ("Remove false clinical-review claim") already stripped the sentence
"This article was created with AI assistance and reviewed for clinical accuracy" from
1,486 files — so the claim was identified as false and a cleanup was attempted.

That cleanup was incomplete. Still live across the corpus:
    "Reviewed by an ICU RN"            "Written by a CRNA Student"
    "Reviewed by a working ICU nurse"  "Written by an ICU nurse on the CRNA path"
    "From Someone Who Works the Floor" "What We Actually Use"
    "Written by critical care nurses who actually use these references"

These are specific, falsifiable assertions of professional review, attached to clinical
content about drug dosing and vasopressor titration, aimed at nurses who may act on it.
An incomplete remediation is worse than an untouched one: the earlier commit establishes
that the claim was known to be false while these copies stayed published.

WHAT IT DOES
Removes the claim while keeping the surrounding text grammatical. Claims appear in four
contexts, all handled:
    1. title parenthetical   "Best Medical AI Apps (Reviewed by an ICU RN) | ICU Notebook"
    2. title suffix          "Best Study Journals — Written by a CRNA Student"
    3. meta description tail "...and scheduling apps. Reviewed by an ICU RN."
    4. body sentence         "<em>Written by an ICU nurse on the CRNA path. See also: ..."
Context 1-2 also appear as LINK TEXT on other pages quoting those titles, so the same
patterns are applied corpus-wide rather than per-page.

This REMOVES false claims; it does not ADD a disclosure. Removing an untrue statement
cannot create new exposure, whereas adding "AI-generated" is a brand decision for the
owner. See add_content_disclaimers.py for the additive half.

IDEMPOTENT. Dry-run by default is NOT used here — pass --dry-run explicitly.

USAGE
    python3 strip_false_credentials.py --dry-run
    python3 strip_false_credentials.py
"""
from __future__ import annotations

import os
import re
import sys

from check_site_integrity import IntegrityError
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

# Curated. Each entry is the CLAIM ITSELF, without surrounding punctuation — the context
# rules below strip the punctuation. Ordered longest-first so a specific claim is consumed
# before a shorter one that is a prefix of it.
#
# Deliberately EXCLUDED as false positives: "reviewed by category", "written by anyone".
CLAIMS = [
    r"This review was written by a CRNA-track ICU nurse and reflects genuine evaluation criteria",
    r"Written by critical care nurses who actually use these references",
    r"By a working travel nurse",
    # participle forms: "...picks chosen by a working ICU nurse.", "...ranked by a working RN."
    r"(?:ranked|chosen|picked|selected|curated|tested|compiled|reviewed|written)"
    r"(?: and (?:ranked|chosen|picked|selected|curated|tested|reviewed))?"
    r" by a working (?:ICU )?(?:nurse|RN)",
    r"Written from the (?:bedside|ICU) nurse(?:'|&#39;|&rsquo;)s perspective",
    r"reviewed and ranked by a working RN",
    r"From an ICU Nurse Who Passed(?: on the first attempt)?",
    r"Written from the floor, not a textbook",
    r"from an ICU nurse who has been there",
    r"Built by a nurse for nurses",
    r"From a Working ICU Nurse",
    r"By a working nurse",
    r"Written by a nurse actively pursuing CRNA school",
    r"Written by an ICU nurse choosing between them",
    r"Written by an ICU nurse on the CRNA path",
    r"written by working nurses \(not finance influencers\)",
    r"Reviewed by a CRNA student(?=[:.,)])",
    r"Written by a nurse, not a marketer",
    r"From Someone Who Works the Floor",
    r"Reviewed by a working ICU nurse",
    r"Written by a KDP publisher",
    r"Reviewed by an ICU nurse",
    r"Written by a CRNA Student",
    r"Reviewed by an ICU RN",
    r"Written by an ICU nurse",
    r"Reviewed by a Nurse",
    r"Reviewed by a nurse",
    r"Written by a nurse",
    r"What We Actually Use",
    # General authorship assertion, listed LAST so the specific phrasings above win first.
    # Scoped to Written/Built/Created + a nursing credential so it cannot swallow legitimate
    # prose like "reviewed by a qualified nursing law attorney" (advice to the reader) or
    # "reviewed by a committee that includes nurses" (describing clinical ladders).
    r"(?:Written|Built|Created|Designed) by an? (?:ICU |travel |working |bedside |critical care )*"
    r"(?:nurse|RN)(?: who [^<.]{0,45})?",
]

CLAIM = "(?:" + "|".join(CLAIMS) + ")"

# Context rules, applied in order. Each removes the claim AND its connective punctuation so
# the result reads naturally rather than leaving "Best Apps () | ICU Notebook".
RULES = [
    # " (Reviewed by an ICU RN)"  ->  ""      [title / link-text parenthetical]
    (re.compile(r"\s*\(" + CLAIM + r"[^)]*\)", re.I), ""),
    # " — from an ICU nurse who has been there."  ->  "."   [dash-joined sentence]
    # Must run before the title-suffix rule: that one is greedy to end-of-title, and would
    # swallow the sentences that legitimately follow this claim inside a meta description.
    (re.compile(r"\s*[—–-]\s*" + CLAIM + r"[^.<\"]*\.", re.I), "."),
    # " — Written by a CRNA Student"  ->  ""  [title suffix, any dash]
    # The quote exclusion matters: without it this runs past the end of a content="..."
    # attribute and eats the closing quote along with unrelated markup.
    (re.compile(r"\s*[—–-]\s*" + CLAIM + r"[^<|\"]*(?=\s*(?:\||<|\"|$))", re.I), ""),
    # ". Reviewed by an ICU RN."  ->  "."     [trailing sentence in meta description / prose]
    (re.compile(r"\.\s*" + CLAIM + r"[^.<\"]*\.", re.I), "."),
    # "Written by an ICU nurse on the CRNA path. "  ->  ""  [leading sentence in an element]
    (re.compile(r"(?<=>)\s*" + CLAIM + r"[^.<]*\.\s*", re.I), ""),
    # " &middot; Written from the ICU nurse's perspective"  ->  ""   [byline separator]
    (re.compile(r"\s*&(?:middot|bull);\s*" + CLAIM, re.I), ""),
    # "...chart room, ranked by a working ICU nurse."  ->  "...chart room."
    # Comma-attached appositive: the comma goes with the claim, or the sentence ends ", ."
    (re.compile(r",\s*" + CLAIM + r"(?=[.<])", re.I), ""),
    # "...picks chosen by a working ICU nurse."  ->  "...picks."
    (re.compile(r"\s+" + CLAIM + r"(?=[.<])", re.I), ""),
    # bare leftover claim with no punctuation scaffold
    (re.compile(r"\s*" + CLAIM + r"\s*", re.I), " "),
]


# Claims that cannot simply be deleted — excision would leave the sentence ungrammatical,
# so the surrounding clause is rewritten instead. Applied before the deletion rules.
REWRITES = [
    (re.compile(r"was built by healthcare and finance professionals to help", re.I),
     "was built to help"),
    # Bolded lead-in; deleting it would leave an empty <strong></strong>.
    (re.compile(r"Written from the bedside:", re.I), "Worth knowing:"),
    # Newsletter promo; deleting the clause mid-sentence breaks it.
    (re.compile(r"weekly updates from an ICU nurse building income streams", re.I),
     "weekly updates on building income streams"),
]

# NOT stripped, deliberately: contact.html states "ICU Notebook is written by Carlos — an
# ICU nurse building passive income on the side while working toward CRNA school." That is a
# site-identity statement about a real, named person on the page whose job is to disclose
# who runs the site. Only the owner knows whether it is accurate, and removing a true
# self-description would be its own kind of wrong. Flagged for the owner instead.


def strip_claims(text: str) -> tuple[str, int]:
    """Return (cleaned_text, number_of_claims_removed)."""
    total = 0
    for pattern, repl in REWRITES:
        text, n = pattern.subn(repl, text)
        total += n
    for pattern, repl in RULES:
        text, n = pattern.subn(repl, text)
        total += n
    # Tidy artifacts the removals can leave behind.
    text = re.sub(r"\s+\|\s*ICU Notebook", " | ICU Notebook", text)
    text = re.sub(r"<title>\s+", "<title>", text)
    text = re.sub(r"\s+</title>", "</title>", text)
    text = re.sub(r'content="\s+', 'content="', text)
    text = re.sub(r'\s+"(?=\s*/?>)', '"', text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)  # no space left before punctuation
    text = re.sub(r"\(\s*\)", "", text)           # no empty parenthetical left behind
    return text, total


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".html"))

    changed = removed = refused = 0
    samples: list[str] = []

    for name in files:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        new_text, n = strip_claims(text)
        if not n or new_text == text:
            continue

        changed += 1
        removed += n
        if len(samples) < 8:
            m = re.search(r"<title>([^<]*)</title>", new_text)
            samples.append(f"    {name}: <title>{(m.group(1) if m else '?')[:70]}</title>")

        if dry:
            continue
        try:
            safe_write_html(path, new_text, allow_preexisting=True)
        except IntegrityError as exc:
            refused += 1
            changed -= 1
            print(f"  REFUSED {name}: {exc}")

    print(f"\n{'[dry-run] ' if dry else ''}pages changed: {changed} | claims removed: {removed} | refused: {refused}")
    if samples:
        print("\n  sample resulting titles:")
        print("\n".join(samples))
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
