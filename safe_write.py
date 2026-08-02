#!/usr/bin/env python3
"""
safe_write.py — atomic, validated writes that make the truncation bug impossible.

WHY THIS EXISTS
`check_site_integrity.py` *detects* a corrupt file after the fact. This module
removes the root cause: the truncation-bug family lands because a partial/cut-off
buffer gets written straight onto the live file, and the damage is only noticed a
session later. Here every write goes to a temp file in the same directory, is
validated while the original is still untouched, and is only swapped into place
with an atomic os.replace() if it passes. A truncated buffer therefore never
becomes the live file — the bad temp is deleted and the caller gets an exception
with the original intact.

This is the "wire the guard into the write path" step the last two Session Briefs
named as the #1 compounding-leverage action.

USAGE
    from safe_write import safe_write_html, safe_write_sitemap, safe_write_text

    safe_write_html("index.html", new_html)        # index.html-aware checks
    safe_write_html("some-article.html", html)     # generic full-HTML checks
    safe_write_sitemap("sitemap.xml", new_xml)     # valid-XML + loc-maps checks
    safe_write_text(path, text, validator=fn)      # any file; fn(path)->list[str]

On failure each raises IntegrityError, the live file is unchanged, and the temp
is cleaned up. On success the file is written atomically (no half-written window).

CLI smoke test:
    python safe_write.py --selftest
"""
from __future__ import annotations

import os
import sys
import tempfile
from typing import Callable, Optional

# Reuse the existing checks so there is ONE source of truth for "what is corrupt".
try:
    from check_site_integrity import (
        IntegrityError,
        check_html_closed,
        check_index,
        check_sitemap,
        html_severity,
        severity_regressions,
        INDEX,
        SITEMAP,
    )
except ImportError:  # allow import when cwd isn't seo_site/
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from check_site_integrity import (  # type: ignore
        IntegrityError,
        check_html_closed,
        check_index,
        check_sitemap,
        html_severity,
        severity_regressions,
        INDEX,
        SITEMAP,
    )

Validator = Callable[[str], list]


def _atomic_write_validated(
    path: str,
    content: str,
    validator: Optional[Validator],
    permit: Optional[Callable[[str], Optional[str]]] = None,
) -> None:
    """
    Write `content` to a temp file beside `path`, validate it, then atomically
    replace `path`. If validation fails, delete the temp and raise — original kept.
    """
    path = os.path.abspath(path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    # Temp lives in the SAME directory so os.replace() is atomic (same filesystem),
    # and so relative-link/loc checks resolve against the real site dir.
    fd, tmp = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())  # ensure the full buffer is on disk before we check it

        if validator is not None:
            problems = validator(tmp)
            if problems:
                # `permit` gives a caller a second say: on an already-corrupt corpus
                # a strict refusal would block every legitimate bulk edit. It returns
                # None to allow the write, or a string explaining the refusal.
                refusal = permit(content) if permit is not None else (
                    "strict validation (no no-regression policy in effect)"
                )
                if refusal is not None:
                    raise IntegrityError(
                        f"Refusing to write {os.path.basename(path)} — {refusal}:\n  - "
                        + "\n  - ".join(problems)
                    )

        os.replace(tmp, path)  # atomic swap; no half-written window on the live file
        tmp = None  # consumed
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def safe_write_html(path: str, content: str, allow_preexisting: bool = False) -> None:
    """
    Atomically write an HTML file, refusing to persist a truncated/unbalanced doc.
    index.html gets the index-specific checks (footer count + no broken card links);
    every other .html gets the generic closed/div-balanced/one-of-each-tag checks.

    allow_preexisting=True switches from "must be clean" to "must be no worse than
    what is already on disk". Bulk mutators need this: ~two thirds of the article
    corpus is already corrupt, so a strict gate would refuse every legitimate edit
    to those files and the mutators would simply go back to bypassing this module.
    The write is still refused the moment it makes any metric worse, which is the
    property that actually matters — corruption can be repaired, never introduced.
    """
    is_index = os.path.abspath(path) == os.path.abspath(INDEX) or \
        os.path.basename(path).lower() == "index.html"
    validator: Validator = (lambda p: check_index(p)) if is_index else (lambda p: check_html_closed(p))

    permit = None
    if allow_preexisting:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                before = html_severity(fh.read())
        except OSError:
            before = None  # new file: nothing to be "no worse than", so stay strict

        def permit(new_content: str) -> Optional[str]:  # noqa: F811
            if before is None:
                return "file is new, so it must be valid"
            worse = severity_regressions(before, html_severity(new_content))
            if worse:
                return "it would make an already-damaged file worse (" + "; ".join(worse) + ")"
            return None

    _atomic_write_validated(path, content, validator, permit)


CURATOR = "build_curated_sitemap.py"

_UNCURATED = (
    "Refusing to write {path}.\n\n"
    "The live sitemap is a deliberate curation, not a dump of the corpus. The site matches "
    "three of Google's four scaled-content-abuse triggers, so advertising every article at "
    "once is manual-action bait; the plan of record calls for a curated batch instead.\n\n"
    f"Only {CURATOR} may write it, and it is the only caller that passes curated=True.\n"
    "  rebuild the recorded batch : python3 " + CURATOR + "\n"
    "  see the writers            : python3 repo_state.py\n\n"
    "Do NOT reach for --target to make this go away. Growing the batch is an owner "
    "decision under scaled-content-abuse risk, not a step in regenerating the sitemap: "
    "--target 1421 would advertise essentially the whole corpus and pass every gate, "
    "which is the outcome this guard exists to prevent.\n\n"
    "If you reached this from generate_sitemap.py, seo_index_sync.py or build_seo_index.py, "
    "that is the guard working: each of those would have replaced the curated sitemap with "
    "a full-corpus one, and no other check would have noticed."
)


def safe_write_sitemap(path: str = SITEMAP, content: str = "", *, curated: bool = False) -> None:
    """
    Atomically write sitemap.xml, refusing invalid XML or dangling <loc> files.

    `curated` is a required opt-in, keyword-only so it cannot be passed by accident.
    Four scripts in this repo call this function and only one of them should: the sitemap
    on disk is a curated subset, and the other three would silently replace it with every
    URL in the corpus. Detecting that after the fact was not enough — the repo's own
    lesson is that a safety module which isn't on the call path is not a safety module —
    so the refusal lives here, at the moment of damage, rather than in a checker that runs
    later and reports what already happened.
    """
    if not curated:
        raise IntegrityError(_UNCURATED.format(path=os.path.basename(path)))
    _atomic_write_validated(path, content, lambda p: check_sitemap(p))


def safe_write_text(path: str, content: str, validator: Optional[Validator] = None) -> None:
    """
    Atomically write any text file (the Session Brief, a .py module, etc.).
    Pass a `validator(path) -> list[str]` to gate the write; with no validator the
    write is still atomic (no half-written window), which alone kills the
    mid-write-truncation-becomes-live failure mode.
    """
    _atomic_write_validated(path, content, validator)


def _selftest() -> int:
    """Prove: a good write lands, a truncated write is rejected, original survives."""
    import re

    failures = 0
    with tempfile.TemporaryDirectory() as d:
        good = (
            "<html><head></head><body>"
            '<div><a href="x.html">card</a></div>'
            "</body></html>"
        )
        # the linked file must exist for the generic check (no broken-link rule there,
        # but article checks don't verify links — index does). Use generic path.
        target = os.path.join(d, "article.html")

        # 1) good write lands
        safe_write_text(target, good, validator=check_html_closed)
        assert os.path.exists(target), "good write did not land"
        assert open(target, encoding="utf-8").read() == good, "content mismatch"
        print("  [1/3] good HTML write landed                          OK")

        # 2) truncated write is rejected, original (the good file) survives untouched
        truncated = '<html><head></head><body><div><a href="x.html">card'  # cut mid-card
        try:
            safe_write_text(target, truncated, validator=check_html_closed)
            print("  [2/3] truncated write was NOT rejected               FAIL")
            failures += 1
        except IntegrityError:
            print("  [2/3] truncated write rejected (IntegrityError)      OK")

        # 3) original file is unchanged after the rejected write
        if open(target, encoding="utf-8").read() == good:
            print("  [3/3] original file intact after rejected write      OK")
        else:
            print("  [3/3] original file was corrupted                    FAIL")
            failures += 1

        # 4) no leftover temp files
        leftovers = [f for f in os.listdir(d) if f.endswith(".tmp")]
        if leftovers:
            print(f"  [!]   leftover temp files: {leftovers}             FAIL")
            failures += 1

    print("SELFTEST", "PASS" if failures == 0 else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
    sys.exit(0)
