"""
Tests for check_article_corpus.py — the CI gate.

A gate nobody has proven can fail is not a gate. These drive main() through each outcome it
is supposed to distinguish: grandfathered damage passes, new damage fails, worsened damage
fails, and repairs are reported rather than punished.

The corpus baseline is now empty — every article is clean — so in practice this gate reads
as "no damaged HTML, ever". The grandfathering machinery is still tested because it is
still what enforces that: an empty baseline means every file must be clean, and the
refusal-to-re-grandfather tests at the bottom are what keep the baseline empty.
"""
import json

import pytest

import check_article_corpus as gate

CLEAN = "<html><head></head><body><div>ok</div></body></html>"
DAMAGED = "<html><head></head><body><div><div>"  # unterminated, div_delta 2
WORSE = "<html><head></head><body><div><div><div>"  # div_delta 3


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "HERE", str(tmp_path))
    monkeypatch.setattr(gate, "BASELINE", str(tmp_path / "tests" / "corpus_baseline.json"))
    return tmp_path


def _write(site, name, content):
    (site / name).write_text(content, encoding="utf-8")


def _baseline(site):
    return json.loads((site / "tests" / "corpus_baseline.json").read_text(encoding="utf-8"))


def test_clean_corpus_with_no_baseline_passes(site):
    _write(site, "a.html", CLEAN)
    assert gate.main() == 0


def test_scan_omits_clean_files(site):
    _write(site, "clean.html", CLEAN)
    _write(site, "bad.html", DAMAGED)
    assert set(gate.scan()) == {"bad.html"}


def test_damage_with_no_baseline_entry_fails(site):
    _write(site, "bad.html", DAMAGED)
    assert gate.main() == 1


def test_baselined_damage_passes(site):
    _write(site, "bad.html", DAMAGED)
    gate.write_baseline(gate.scan())
    assert gate.main() == 0


def test_worsening_a_baselined_file_fails(site):
    _write(site, "bad.html", DAMAGED)
    gate.write_baseline(gate.scan())
    _write(site, "bad.html", WORSE)
    assert gate.main() == 1


def test_improving_a_baselined_file_passes(site):
    _write(site, "bad.html", WORSE)
    gate.write_baseline(gate.scan())
    _write(site, "bad.html", DAMAGED)
    assert gate.main() == 0


def test_fully_repairing_a_baselined_file_passes(site):
    _write(site, "bad.html", DAMAGED)
    gate.write_baseline(gate.scan())
    _write(site, "bad.html", CLEAN)
    assert gate.main() == 0


def test_a_new_damaged_file_fails_even_when_others_are_baselined(site):
    _write(site, "old.html", DAMAGED)
    gate.write_baseline(gate.scan())
    _write(site, "new.html", DAMAGED)
    assert gate.main() == 1


def test_update_baseline_records_only_damaged_files(site, monkeypatch):
    _write(site, "clean.html", CLEAN)
    _write(site, "bad.html", DAMAGED)
    monkeypatch.setattr(
        "sys.argv", ["check_article_corpus.py", "--update-baseline", "--allow-new-damage"]
    )

    assert gate.main() == 0
    files = _baseline(site)["files"]
    assert set(files) == {"bad.html"}
    assert files["bad.html"]["div_delta"] == 2


def test_update_baseline_locks_in_a_repair(site, monkeypatch):
    """The normal use: damage is fixed, and the improvement becomes the new floor."""
    _write(site, "bad.html", DAMAGED)
    gate.write_baseline(gate.scan())
    _write(site, "bad.html", CLEAN)

    monkeypatch.setattr("sys.argv", ["check_article_corpus.py", "--update-baseline"])
    assert gate.main() == 0
    assert _baseline(site)["files"] == {}

    # And the repair can no longer silently regress.
    monkeypatch.setattr("sys.argv", ["check_article_corpus.py"])
    _write(site, "bad.html", DAMAGED)
    assert gate.main() == 1


# --- the baseline may only ever move DOWN -----------------------------------


def test_update_baseline_refuses_to_grandfather_new_damage(site, monkeypatch):
    """
    The one way a green gate could quietly stop meaning anything: re-record fresh damage
    as the new floor. It has to be refused, or the gate launders every regression that
    follows it.
    """
    _write(site, "bad.html", DAMAGED)
    monkeypatch.setattr("sys.argv", ["check_article_corpus.py", "--update-baseline"])

    assert gate.main() == 1
    assert not (site / "tests" / "corpus_baseline.json").exists()


def test_update_baseline_refuses_to_record_a_worsened_file(site, monkeypatch):
    _write(site, "bad.html", DAMAGED)
    gate.write_baseline(gate.scan())
    _write(site, "bad.html", WORSE)

    monkeypatch.setattr("sys.argv", ["check_article_corpus.py", "--update-baseline"])
    assert gate.main() == 1
    assert _baseline(site)["files"]["bad.html"]["div_delta"] == 2  # unchanged


def test_allow_new_damage_overrides_the_refusal(site, monkeypatch):
    _write(site, "bad.html", DAMAGED)
    monkeypatch.setattr(
        "sys.argv", ["check_article_corpus.py", "--update-baseline", "--allow-new-damage"]
    )
    assert gate.main() == 0

    monkeypatch.setattr("sys.argv", ["check_article_corpus.py"])
    assert gate.main() == 0


def test_non_html_files_are_ignored(site):
    _write(site, "notes.txt", DAMAGED)
    assert gate.scan() == {}
    assert gate.main() == 0
