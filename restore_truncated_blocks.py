#!/usr/bin/env python3
"""
restore_truncated_blocks.py — put back article text that a truncated write deleted.

WHY THIS EXISTS
Seven articles stop mid-sentence or mid-list, and the trailing injected blocks were then
appended right on top of the cut. What is missing is not boilerplate — it is prose and
list items the site is meant to be publishing:

    403b-for-nurses-complete-guide-2026            6 checklist items + the tax disclaimer
    cheap-vet-care-options                         the last checklist item
    nurse-side-hustles-2026                        the last two rows of the comparison table
    nurse-side-hustles-that-actually-pay-2026      a closing </p>
    pslf-for-nurses-complete-guide-2026            the rest of the "rules change" disclaimer
    travel-nurse-pay-2026-complete-breakdown       two closing paragraphs
    travel-nurse-taxes-complete-guide-2026         4 checklist items + the closing paragraph

Every fragment below was recovered from git history, from the newest revision of that file
whose block tags still balanced (ca91ea4b in all seven cases — the damage came in with the
1,111-conflict merge at 200c3c77). Nothing here is written by this repair; the strings are
the repository's own earlier bytes.

WHAT WAS DELIBERATELY NOT RESTORED
The historical revisions also contain page furniture the site has since replaced: an
ARIA-Capital-era affiliate disclosure, "related-box" cards whose links are `href="#"`
placeholders, and a CTA pointing at `#GUMROAD_SIDE_HUSTLE_TRACKER`. Bringing those back
would re-publish dead links and a retired brand, so each recovered tail is cut at the first
line that opens a <div>, a comment, or an `href="#"` link. Only prose, list items and table
rows are restored.

Eleven further files are truncated the same way but have no revision in history where the
block still closes, so there is nothing to restore from and they are left alone — see the
Known issues section of CLAUDE.md.

HOW IT IS SAFE
Each entry is (anchor, tail). The anchor is the surviving text at the cut, and it must
appear in the file exactly once or the entry is skipped. The tail is inserted immediately
after it and nothing else in the document is touched, so the repair can only ever append
the missing bytes at the point where the write stopped.

IDEMPOTENT — an anchor already followed by its tail is skipped.

USAGE
    python3 restore_truncated_blocks.py --dry-run
    python3 restore_truncated_blocks.py
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

from check_site_integrity import html_severity, severity_regressions
from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))

BLOCK_TAGS = ("main", "article", "table", "ol", "ul")


@dataclass(frozen=True)
class Restoration:
    """`tail` goes immediately after the single occurrence of `anchor`, or nothing happens."""

    filename: str
    anchor: str
    tail: str


RESTORATIONS = [
    # 403b-for-nurses-complete-guide-2026.html — recovered from ca91ea4b
    Restoration(
        '403b-for-nurses-complete-guide-2026.html',
        anchor='    <li style="margin-bottom: 10px;">Ask HR: what is the match rate and minimum contribution required to capture it fully?</li>',
        tail='\n    <li style="margin-bottom: 10px;">Confirm your contribution is at least high enough to get the full match — increase it immediately if not</li>\n    <li style="margin-bottom: 10px;">Check your investment menu for expense ratios — look for index funds under 0.20%</li>\n    <li style="margin-bottom: 10px;">Ask HR whether the hospital also offers a 457(b)</li>\n    <li style="margin-bottom: 10px;">If pursuing PSLF: switch to Traditional (pre-tax) contributions to lower your AGI and IDR payment</li>\n    <li style="margin-bottom: 10px;">Use the waterfall to determine your next contribution increase</li>\n    <li style="margin-bottom: 10px;">Check your vesting schedule before making any job change decisions</li>\n  </ul>\n\n  <p style="margin-top: 32px; color: var(--text-muted); font-size: 0.9rem;"><em>This guide reflects 403(b) rules and IRS limits for 2026. Tax law and contribution limits change annually — verify current figures at irs.gov/retirement-plans. This is not financial or tax advice; consult a fee-only financial advisor for guidance specific to your situation.</em></p>\n\n</main>',
    ),
    # cheap-vet-care-options.html — recovered from ca91ea4b
    Restoration(
        'cheap-vet-care-options.html',
        anchor='  <li>Save the number for your nea',
        tail='rest veterinary school teaching hospital</li>\n</ol>',
    ),
    # nurse-side-hustles-2026.html — recovered from ca91ea4b
    Restoration(
        'nurse-side-hustles-2026.html',
        anchor='      <td>$45-85/hr</td>\n      <td>High</td>\n      <td>Moderate</td>',
        tail='\n      <td>1-3 months</td>\n    </tr>\n    <tr>\n      <td>Clinical Adjunct Faculty</td>\n      <td>$25-60/hr</td>\n      <td>Moderate</td>\n      <td>Limited</td>\n      <td>1-2 months</td>\n    </tr>\n  </tbody>\n</table>',
    ),
    # nurse-side-hustles-that-actually-pay-2026.html — recovered from ca91ea4b
    Restoration(
        'nurse-side-hustles-that-actually-pay-2026.html',
        anchor='    <p>Know your actual hourly rate. Protect it. Build from there.',
        tail='</p>',
    ),
    # pslf-for-nurses-complete-guide-2026.html — recovered from ca91ea4b
    Restoration(
        'pslf-for-nurses-complete-guide-2026.html',
        anchor='  <p style="margin-top: 32px; color: var(--text-muted); font-size: 0.9rem;"><em>This guide reflects PSLF',
        tail=' rules as of 2026. Federal student loan rules can change. Always verify current rules at studentaid.gov or with a certified student loan advisor before making decisions.</em></p>\n\n</main>',
    ),
    # travel-nurse-pay-2026-complete-breakdown.html — recovered from ca91ea4b
    Restoration(
        'travel-nurse-pay-2026-complete-breakdown.html',
        anchor='  <p>Travel nursing pays well. But it pays well in a specific way: large chunks of your compensation are non-taxable stipends, not wages. That structure means your take-home percentage is higher than most jobs — but only if you understand how it works and qualify for the tax treatment.',
        tail='</p>\n\n  <p>The three things to nail before signing your first (or next) contract: know your taxable base rate, confirm your stipends are GSA-compliant for the city, and have a real tax home to maintain. Do those three things and the pay math works in your favor. Skip any one of them and you\'ll end up with a tax bill that erases the premium you thought you were earning.</p>\n\n  <p>For the full tax picture — including the tax home rules, how to handle quarterly estimated taxes, and which deductions travel nurses actually qualify for — read our <a href="travel-nurse-taxes-complete-guide-2026.html">Travel Nurse Tax Complete Guide</a>.</p>',
    ),
    # travel-nurse-taxes-complete-guide-2026.html — recovered from ca91ea4b
    Restoration(
        'travel-nurse-taxes-complete-guide-2026.html',
        anchor='    <li>Know which s',
        tail="tate you'll be filing in for each assignment.</li>\n    <li>If you're 1099, pay quarterly estimates — don't wait until April.</li>\n    <li>Hire a travel-nurse-specialist CPA if your stipend income is substantial or your situation is complex.</li>\n    <li>Use the extra income strategically: emergency fund, Solo 401(k), Roth IRA, student loans.</li>\n  </ol>\n\n  <p>The financial case for travel nursing is strong when you run the real numbers. But it only holds up when the tax strategy underneath it is sound. A nurse who earns $120,000/year as a traveler and loses $25,000 to a preventable tax audit effectively earned $95,000 — which a well-structured staff position might have matched. Do the work upfront. The math rewards you for it.</p>",
    ),
]

def block_balance(html: str) -> dict[str, int]:
    """Unclosed count per block tag. All zeros is what a well-formed article looks like."""
    return {
        t: len(re.findall(r"<%s\b" % t, html)) - html.count("</%s>" % t)
        for t in BLOCK_TAGS
    }


def apply(html: str, r: Restoration) -> str | None:
    """Repaired document, or None if the anchor is missing/ambiguous or already restored."""
    if html.count(r.anchor) != 1:
        return None
    at = html.index(r.anchor) + len(r.anchor)
    if html[at:at + len(r.tail)] == r.tail:
        return None  # already restored
    return html[:at] + r.tail + html[at:]


def main() -> int:
    dry = "--dry-run" in sys.argv
    done: list[str] = []
    skipped: list[str] = []

    for r in RESTORATIONS:
        path = os.path.join(HERE, r.filename)
        if not os.path.exists(path):
            skipped.append(f"{r.filename}: no such file")
            continue
        with open(path, encoding="utf-8") as fh:
            before = fh.read()

        after = apply(before, r)
        if after is None:
            continue

        worse = [
            f"{t}: {b} -> {a}"
            for t, b, a in (
                (t, block_balance(before)[t], block_balance(after)[t]) for t in BLOCK_TAGS
            )
            if abs(a) > abs(b)
        ]
        worse += severity_regressions(html_severity(before), html_severity(after))
        if worse:
            skipped.append(f"{r.filename}: refused, would regress — " + "; ".join(worse))
            continue

        done.append(f"{r.filename}: +{len(r.tail)} bytes of article text")
        if not dry:
            safe_write_html(path, after, allow_preexisting=True)

    verb = "would restore" if dry else "restored"
    print(f"{verb}: {len(done)} file(s)")
    for line in done:
        print("  +", line)
    if skipped:
        print(f"skipped: {len(skipped)} file(s)")
        for line in skipped:
            print("  -", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
