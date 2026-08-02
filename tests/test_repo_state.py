"""
Tests for repo_state.py — the state reporter CLAUDE.md now tells sessions to trust.

A reporter that drifts is worse than no reporter, because the whole point is that a
session believes it instead of re-deriving by hand. So the tests pin the two things that
would make it lie: it must never write, and its numbers must match what the gates and the
tree actually say.
"""
import os
import re

import repo_state as R

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_it_runs_and_reports_success(capsys):
    assert R.main() == 0
    assert "corpus" in capsys.readouterr().out


def test_it_writes_nothing(capsys):
    """A reporter that mutates the tree would be a trap — this is the whole contract."""
    before = {
        name: os.stat(os.path.join(HERE, name)).st_mtime
        for name in os.listdir(HERE)
        if name.endswith((".html", ".xml", ".txt", ".yml", ".json"))
    }
    R.main()
    capsys.readouterr()
    after = {name: os.stat(os.path.join(HERE, name)).st_mtime for name in before}
    assert before == after


def test_source_cannot_write():
    """
    Belt and braces on the contract above. The module both names safe_write_sitemap in a
    comment and matches it in a regex, so "is the string present" is the wrong question.
    The right one is whether it can reach a writer at all: no safe_write import, and no
    file opened in a writing mode.
    """
    src = open(os.path.join(HERE, "repo_state.py"), encoding="utf-8").read()
    assert not re.search(r"^\s*(?:from safe_write import|import safe_write)", src, re.M)
    assert not re.search(r"""open\([^)]*['"][wax]""", src)


# --- the numbers must match reality -----------------------------------------


def _can_write_sitemap(src: str) -> bool:
    """Imports the writer AND calls it — merely naming it in prose does not count."""
    return bool(
        re.search(r"^\s*from safe_write import[^\n]*safe_write_sitemap", src, re.M)
        and re.search(r"safe_write_sitemap\s*\(", src)
    )


def test_a_module_that_only_mentions_the_writer_is_not_counted():
    """check_sitemap_curated.py discusses safe_write_sitemap in its docstring."""
    assert "check_sitemap_curated.py" not in R.sitemap_writers()


def test_sitemap_writers_finds_every_script_that_can_rewrite_the_sitemap():
    """
    The curated 940-URL sitemap is a deliberate decision three legacy scripts would
    silently revert. If this under-reports, the hazard goes quiet.
    """
    expected = {
        name
        for name in os.listdir(HERE)
        if name.endswith(".py")
        and name not in ("safe_write.py", "repo_state.py")
        and _can_write_sitemap(open(os.path.join(HERE, name), encoding="utf-8").read())
    }
    assert set(R.sitemap_writers()) == expected
    assert "build_curated_sitemap.py" in expected


def test_monetization_matches_ads_txt():
    """One publisher, and it must be the one ads.txt authorizes."""
    money = R.monetization()
    ads_txt = re.findall(r"(pub-[0-9]+)", R._read("ads.txt"))
    assert money["publisher_ids"] == ads_txt


def test_only_one_amazon_tag():
    assert len(R.monetization()["amazon_tags"]) <= 1


def test_truncated_articles_are_still_the_known_three():
    """
    If one of these gets finished, this fails and the note gets updated with it — which
    is the point, since a stale note is how this section went wrong three times.
    """
    assert R.truncated_articles() == [
        "best-icu-nursing-books-2026.html",
        "new-grad-nurse-financial-survival-guide.html",
        "roth-ira-for-nurses-complete-guide.html",
    ]


def test_reported_article_count_matches_the_tree():
    assert len(R._articles()) == len([n for n in os.listdir(HERE) if n.endswith(".html")])
