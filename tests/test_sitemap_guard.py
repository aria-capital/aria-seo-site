"""
Tests for the two-layer sitemap guard.

The curated sitemap is a business decision — the site matches three of Google's four
scaled-content-abuse triggers, so advertising the whole corpus is manual-action bait. Three
scripts in this repo would revert that decision silently, and no check noticed.

Layer 1 is safe_write_sitemap(curated=...), which refuses at the moment of damage.
Layer 2 is check_sitemap_curated.py, the backstop for writes that never touch safe_write.

The tests that matter most are the ones proving the three legacy writers are actually
stopped, because "the guard exists" and "the guard is on the call path" are the two claims
this repo has confused before.
"""
import os
import re
import subprocess
import sys

import pytest

import build_curated_sitemap as B
import check_sitemap_curated as G
from check_site_integrity import IntegrityError
from safe_write import safe_write_sitemap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITEMAP_TMPL = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'
)


# --- layer 1: the write path -------------------------------------------------


def test_an_uncurated_sitemap_write_is_refused(tmp_path):
    out = tmp_path / "sitemap.xml"
    with pytest.raises(IntegrityError, match="Refusing to write"):
        safe_write_sitemap(str(out), SITEMAP_TMPL.format(rows=""))
    assert not out.exists(), "the refusal must happen before anything is written"


def test_the_refusal_names_the_only_legitimate_writer(tmp_path):
    """A guard whose message does not say what to do instead gets worked around."""
    with pytest.raises(IntegrityError) as exc:
        safe_write_sitemap(str(tmp_path / "sitemap.xml"), "")
    assert "build_curated_sitemap.py" in str(exc.value)


def test_curated_cannot_be_passed_positionally(tmp_path):
    """Keyword-only, so no caller enables it by accident through argument drift."""
    with pytest.raises(TypeError):
        safe_write_sitemap(str(tmp_path / "sitemap.xml"), "", True)


def test_the_curator_itself_still_writes(tmp_path, monkeypatch):
    import check_site_integrity as csi

    monkeypatch.setattr(csi, "SITE_DIR", str(tmp_path))
    (tmp_path / "real.html").write_text(
        "<html><head></head><body><div>x</div></body></html>", encoding="utf-8"
    )
    xml = SITEMAP_TMPL.format(rows="  <url><loc>https://x.test/real.html</loc></url>")
    out = tmp_path / "sitemap.xml"
    safe_write_sitemap(str(out), xml, curated=True)
    assert out.exists()


# --- layer 1, the part that actually matters: the legacy writers are stopped --


@pytest.mark.parametrize("module", ["generate_sitemap", "seo_index_sync", "build_seo_index"])
def test_legacy_writers_do_not_pass_the_curated_flag(module):
    """
    Source-level check, so it holds even for the code paths these tests do not execute.
    If a future session "fixes" one of these by adding curated=True, this fails and makes
    them explain themselves.
    """
    src = open(os.path.join(HERE, f"{module}.py"), encoding="utf-8").read()
    for call in re.findall(r"safe_write_sitemap\s*\([^)]*\)", src, re.S):
        assert "curated" not in call, f"{module} must not opt itself into writing the sitemap"


def test_only_the_curator_opts_in():
    """Exactly one file in the repo may pass curated=True."""
    optees = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name == "safe_write.py":
            continue
        src = open(os.path.join(HERE, name), encoding="utf-8").read()
        if re.search(r"safe_write_sitemap\s*\([^)]*curated\s*=\s*True", src, re.S):
            optees.append(name)
    assert optees == ["build_curated_sitemap.py"]


def test_generate_sitemap_build_now_raises_instead_of_reverting():
    """
    The concrete regression. Before the guard, calling build() — even just to inspect the
    output — rewrote the live sitemap with all 1,461 URLs. It bit a real session.
    """
    import generate_sitemap

    with pytest.raises(IntegrityError, match="Refusing to write"):
        generate_sitemap.build()


def test_the_live_sitemap_is_untouched_by_that_call():
    """Belt and braces on the test above: the refusal must not be a partial write."""
    with open(os.path.join(HERE, "sitemap.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    assert xml.count("<loc>") < 1200, "a full-corpus dump would be ~1,461"


# --- layer 2: the CI backstop ------------------------------------------------


def test_gate_passes_on_the_live_sitemap():
    assert G.problems() == []
    assert G.main() == 0


def test_gate_fails_when_a_thin_article_is_advertised(monkeypatch, tmp_path):
    """The disaster this exists to catch: a full-corpus dump advertises the thin pages."""
    thin = G.thin_articles()
    assert thin, "the corpus must contain thin articles or this gate proves nothing"
    victim = sorted(thin)[0]

    fake = tmp_path / "sitemap.xml"
    fake.write_text(
        SITEMAP_TMPL.format(rows=f"  <url><loc>https://x.test/{victim}</loc></url>"),
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "SITEMAP", str(fake))
    found = G.problems()
    assert len(found) == 1 and victim in found[0]
    assert G.main() == 1


def test_gate_exempts_the_core_navigation_pages():
    """
    about.html and affiliate-disclosure.html are under the word floor and are advertised on
    purpose — they are navigation, not ranked content. A gate that flagged them would be
    red forever, which is how gates get ignored.
    """
    assert set(B.CORE_PAGES) & set(G.advertised_slugs(open(
        os.path.join(HERE, "sitemap.xml"), encoding="utf-8").read()))
    assert not set(B.CORE_PAGES) & set(G.thin_articles())


def test_gate_survives_the_curator_widening_its_batch():
    """
    A bigger batch is a legitimate owner decision. It still excludes thin pages, so the
    gate must not fire — otherwise widening means fighting CI.
    """
    names, _ = B.select(1200)
    thin = G.thin_articles()
    assert not (set(names) & set(thin))


def test_gate_is_stable_against_lastmod_drift():
    """
    Why this gate asserts an invariant rather than comparing to the curator's output:
    <lastmod> is date.today(), so byte-equality would pass the day it was written and fail
    every day after.
    """
    curator = open(os.path.join(HERE, "build_curated_sitemap.py"), encoding="utf-8").read()
    assert "date.today()" in curator

    # The gate explains date.today() in its docstring, so "is the string present" is the
    # wrong question — the right one is whether it can depend on the clock at all.
    gate = open(os.path.join(HERE, "check_sitemap_curated.py"), encoding="utf-8").read()
    assert not re.search(r"^\s*(?:from datetime import|import datetime|import time)", gate, re.M)
    assert "<lastmod>" not in G.problems.__doc__ if G.problems.__doc__ else True


def test_gate_runs_as_a_script():
    """It is a CI step; it has to work from the command line, not just as an import."""
    r = subprocess.run([sys.executable, "check_sitemap_curated.py"], cwd=HERE,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout
