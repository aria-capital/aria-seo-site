"""
Tests for fix_pediatric_dose_column_header.py, plus a corpus guard on the class.

The guard is the interesting part and it bans a CLASS rather than a string: no table column
headed "Maximum Single Dose" (or "Max Single Dose") may contain a cell whose figure is per-DAY.
It needs no drug list, so it keeps working on tables nobody has audited and on pages that do
not exist yet — the same shape as the arithmetic and DKA-threshold guards.

It is also deliberately narrow in one way worth stating: it does not require the column to be
renamed, only that the header and the cells agree. A page that keeps "Maximum Single Dose" and
genuinely holds only per-dose figures passes. The invariant is internal consistency, not
conformity to a wording chosen here.
"""
import glob
import html
import os
import re

import pytest

import fix_pediatric_dose_column_header as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CORPUS = None


def corpus():
    global _CORPUS
    if _CORPUS is None:
        out = []
        for p in sorted(glob.glob(os.path.join(REPO, "*.html"))):
            with open(p, encoding="utf-8", errors="replace") as fh:
                out.append((os.path.basename(p), fh.read()))
        _CORPUS = out
    return _CORPUS


SINGLE_DOSE_HEADER = re.compile(r"<th[^>]*>\s*(?:Maximum|Max)\.?\s+Single\s+Dose\s*</th>", re.I)
PER_DAY = re.compile(r"/\s*day|per\s+day|/\s*24\s*h(?:r|ours?)?\b", re.I)


def header_row_conflicts(text):
    """Tables whose 'Maximum Single Dose' column holds a per-day figure.

    Finds the column index of such a header, then reads that same index out of every body row.
    Indexing by position matters: a naive "does this table mention /day anywhere" check would
    fire on the TYPICAL-dose column, which legitimately carries mg/kg/day figures.
    """
    bad = []
    for table in re.findall(r"<table.*?</table>", text, re.S | re.I):
        rows = re.findall(r"<tr.*?</tr>", table, re.S | re.I)
        if not rows:
            continue
        head = re.findall(r"<t[dh][^>]*>.*?</t[dh]>", rows[0], re.S | re.I)
        idx = next((i for i, c in enumerate(head) if SINGLE_DOSE_HEADER.search(c)), None)
        if idx is None:
            continue
        for row in rows[1:]:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
            if len(cells) <= idx:
                continue
            cell = html.unescape(re.sub(r"<[^>]+>", "", cells[idx])).strip()
            if PER_DAY.search(cell):
                bad.append(cell[:70])
    return bad


def test_the_corpus_is_not_empty():
    """Positive control for the scan below."""
    assert len(corpus()) > 1000, "article glob found almost nothing — the guard is blind"


def test_every_edit_names_a_real_file():
    for path, _old, _new, _why, _src in F.EDITS:
        assert os.path.exists(os.path.join(REPO, path)), f"{path} does not exist"


def test_the_repair_is_idempotent_against_the_live_tree():
    for path, old, _new, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert fh.read().count(old) == 0, f"{path}: pre-repair text is still present"


def test_every_replacement_landed():
    for path, _old, new, _why, _src in F.EDITS:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            assert new in fh.read(), f"{path}: corrected wording is missing"


def test_the_repair_changed_no_clinical_figure():
    """The property that makes this safe without a clinician: it is a header deletion. No digit
    anywhere in the edit."""
    for _path, old, new, _why, _src in F.EDITS:
        assert not re.search(r"\d", old + new), "this repair must not touch any number"


def test_every_dose_cell_on_the_page_still_labels_its_own_unit():
    """Renaming the header is only safe because each cell says /day or /dose itself. If that
    ever stops being true, the column becomes ambiguous and the rename becomes a loss."""
    with open(os.path.join(REPO, "pediatric-medication-dosing-guide-2026.html"), encoding="utf-8") as fh:
        text = fh.read()
    table = next(t for t in re.findall(r"<table.*?</table>", text, re.S | re.I) if "Morphine" in t)
    rows = re.findall(r"<tr.*?</tr>", table, re.S | re.I)
    head = re.findall(r"<t[dh][^>]*>.*?</t[dh]>", rows[0], re.S | re.I)
    idx = next(i for i, c in enumerate(head) if "Maximum Dose" in c)
    for row in rows[1:]:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if len(cells) <= idx:
            continue
        cell = html.unescape(re.sub(r"<[^>]+>", "", cells[idx]))
        assert re.search(r"/\s*day|per\s+day|/\s*dose|per\s+dose|/24hr", cell, re.I), (
            f"cell no longer states its own basis: {cell[:70]!r}"
        )


# --- the guard that outlives the repair ----------------------------------------------------

def test_no_single_dose_column_anywhere_holds_a_per_day_figure():
    """Corpus-wide, and it compares a table against ITSELF rather than against a remembered
    convention."""
    offenders = []
    for name, text in corpus():
        for cell in header_row_conflicts(text):
            offenders.append(f"{name}: {cell!r}")
    assert offenders == [], (
        "a 'Maximum Single Dose' column holds a per-day figure:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_can_go_red_on_the_table_that_was_live():
    planted = ("<table><tr><th>Medication</th><th>Typical Pediatric Dose</th>"
               "<th>Maximum Single Dose</th></tr>"
               "<tr><td>Acetaminophen</td><td>10&ndash;15 mg/kg every 4&ndash;6 hours</td>"
               "<td>75 mg/kg/day (max 5 doses/24hr)</td></tr></table>")
    assert header_row_conflicts(planted), "detector failed on the exact table that was live"


def test_the_guard_stays_silent_once_the_header_is_honest():
    fixed = ("<table><tr><th>Medication</th><th>Typical Pediatric Dose</th>"
             "<th>Maximum Dose</th></tr>"
             "<tr><td>Acetaminophen</td><td>10&ndash;15 mg/kg every 4&ndash;6 hours</td>"
             "<td>75 mg/kg/day (max 5 doses/24hr)</td></tr></table>")
    assert header_row_conflicts(fixed) == []


def test_the_guard_does_not_fire_on_a_genuinely_single_dose_column():
    """Crying-wolf control. A table that keeps the stricter header and earns it must PASS —
    the invariant is header/cell agreement, not a wording chosen by this repo."""
    honest = ("<table><tr><th>Medication</th><th>Maximum Single Dose</th></tr>"
              "<tr><td>Ondansetron</td><td>4 mg/dose (&lt;40 kg)</td></tr>"
              "<tr><td>Dexamethasone</td><td>10 mg/dose for croup</td></tr></table>")
    assert header_row_conflicts(honest) == []


def test_the_guard_reads_the_right_column():
    """The failure this detector was most likely to have: firing on the TYPICAL-dose column,
    which legitimately carries mg/kg/day. Indexing by header position is what prevents it."""
    typical_is_per_day = ("<table><tr><th>Medication</th><th>Typical Pediatric Dose</th>"
                          "<th>Maximum Single Dose</th></tr>"
                          "<tr><td>Amoxicillin</td><td>40&ndash;90 mg/kg/day &divide; q8&ndash;12h</td>"
                          "<td>500 mg/dose</td></tr></table>")
    assert header_row_conflicts(typical_is_per_day) == [], (
        "guard fired on the typical-dose column, which may legitimately be per-day"
    )
