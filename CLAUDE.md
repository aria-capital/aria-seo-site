# CLAUDE.md — working notes for this repo

Read this before changing anything. It records what broke here, why, and the rules that
keep it from breaking again. Most of it was learned the expensive way.

## What this repo is

A static SEO/affiliate site deployed via GitHub Pages: ~1,461 hand-generated HTML articles
(ICU nursing, nursing careers, personal finance) monetized with Google AdSense, Amazon
Associates, and affiliate programs. There is no build step and no runtime dependency — the
HTML *is* the product. A handful of Python scripts generate and bulk-edit those files.

Because the HTML is the product, a script that corrupts HTML corrupts the business. That
framing drives every rule below.

## Architecture

**Guards (`check_site_integrity.py`, `safe_write.py`)**
- `check_site_integrity.py` is the single source of truth for "what is corrupt". Everything
  else defers to it. `html_severity()` returns comparable metrics; `severity_regressions()`
  compares two of them.
- `safe_write.py` is the only sanctioned write path. It writes to a temp file in the same
  directory, validates it, then `os.replace()`s it into place. A bad buffer never becomes
  the live file.

**Mutators** — `inject_shared_css.py`, `inject_affiliate_links.py`, `_wire_hubs.py`,
`seo_index_sync.py`, `apply_affiliate_tag.py`, `fix_cookie_banner.py`. These rewrite
existing articles in bulk.

**Generators** — `build_seo_index.py`, `build_article_hub.py`, `generate_sitemap.py`.
These create files from scratch.

**Gates** — `check_article_corpus.py` (CI) and `tests/` (121 tests, pytest).

## Rules

1. **Never write HTML with `open(..., 'w')`.** Use `safe_write_html` / `safe_write_sitemap`
   / `safe_write_text`. This is not style — see "The truncation bug" below.
2. **Bulk edits to existing articles use `allow_preexisting=True`.** Generated-from-scratch
   files use strict mode. Rationale in the next section.
3. **Every bulk mutator must be idempotent**, and must have a test proving it. These scripts
   get re-run casually. A non-idempotent injector stacks duplicate content across 1,400 files
   on the second run, and nobody notices until it's in the index.
4. **Every bulk mutator needs a `--dry-run`** that writes nothing.
5. **Never fabricate article content in a repair.** Losing a truncated fragment is acceptable;
   inventing links, prices, or clinical text is not. If a repair cannot be done without
   inventing content, skip the file and report it.
6. **Run `python check_article_corpus.py` before pushing.** CI runs it too, but the feedback
   is faster locally.

## The truncation bug — the defining failure of this codebase

A family of writers were cut off mid-write, leaving partial buffers as live files. It hit
`index.html`, `sitemap.xml`, and hundreds of articles, repeatedly, over months. Each
occurrence was found a session later, by hand.

`safe_write.py` was written specifically to end this — and then **was imported by nothing**
for its entire existence. All eight mutators kept using raw `open(..., 'w')`. When the guard
was finally wired in, 980 of 1,461 articles were already corrupt.

Two lessons, both generalizable:

- **A safety module that isn't on the call path is not a safety module.** It was written,
  self-tested, documented as "the #1 compounding-leverage action" — and did nothing, because
  nothing called it. Check the call graph, not the file listing.
- **A guard nobody runs is not a guard.** `check_site_integrity.py` had correctly reported
  the site as broken for months. There was no CI, so nothing read the output.

### Why the gates grandfather existing damage

Two thirds of the corpus was already corrupt when the guards went live. A gate demanding
cleanliness would have been red on every build from day one, and a permanently-red gate is
one everyone learns to ignore — the same failure mode that let the bug run for months.

So both gates compare against a recorded floor instead:
- `safe_write(allow_preexisting=True)` refuses a write only if it makes a metric *worse*.
- `check_article_corpus.py` fails only if a file regresses past `tests/corpus_baseline.json`,
  or if a file with no baseline entry is anything but clean.

Existing damage is paid down at leisure; new damage is impossible. **After repairing files,
run `python check_article_corpus.py --update-baseline`** so the improvement becomes the new
floor and can never silently regress.

### Repair pattern that works

The cookie-banner repair (599 files) is the template for this class of fix:
1. Identify the damaged region by its start marker and the first *following sibling* marker.
   Sibling markers work because the damaged block contains none of them, so one rule handles
   every cut point.
2. Excise the region, re-emit a canonical copy taken verbatim from a known-good file.
3. Make the no-op case exact (`region == CANONICAL`) so re-running changes nothing.
4. Write through `safe_write_html(..., allow_preexisting=True)`.
5. Verify with a corpus-wide severity scan before and after, and by re-running for idempotency.

## Known issues (as of the test-coverage work)

Documented by tests rather than fixed, to keep changes reviewable:

- **322 articles still truncated**, cut inside their trailing injected-block region. Article
  content is intact; `</body></html>` is lost.
- **`index.html` is damaged** — unbalanced divs, missing `</footer>`. `check_site_integrity.py`
  fails on it, so CI runs that check non-blocking. Flip it to required once repaired.
- **AdSense pub ID mismatch**: `ads.txt` declares `pub-6510170611627184`, pages serve
  `ca-pub-5576001602612111`. Only the owner knows which account is real.
- **Two Amazon associate tags** live simultaneously (`ariacapital-20`, `aria-affiliate-20`).
  One of them earns nothing.
- **`?via=aria` affiliate links** appear to be unreplaced placeholders.
- **Two scripts both write `sitemap.xml`** (`generate_sitemap.py`, `seo_index_sync.py`) with
  different base URLs and different schemas. Last one to run wins. Unresolved.
- **`generate_sitemap.read_base_url()` falls back to a host that is no longer the deployed
  host** — a missing `_config.yml` would point the whole sitemap at the wrong domain.
- **`seo_index_sync.linked_in_index()` matches only `[a-z0-9-]` hrefs**, so underscored
  filenames read as unlinked and get re-added as orphan cards on every run.
- **192 articles lack `rel="canonical"`; 13 clinical articles lack disclaimer language.**
- **1,255 `.fuse_hidden*` files are committed** — orphans from unclean FUSE unmounts, not
  byte-identical to any live article. Junk, but tracked, so removal is the owner's call.
- **Three brand identities**: `_config.yml` says "Money Psychology", footers say "ICU
  Notebook", the org is "aria-capital".

## Commands

```bash
python -m pytest -q                              # 121 tests
python check_article_corpus.py                   # CI gate (regression, not cleanliness)
python check_article_corpus.py --update-baseline # after repairing files
python check_site_integrity.py                   # index.html + sitemap.xml (currently fails)
python fix_cookie_banner.py --dry-run            # every mutator has a dry run
```

## Environment note

The `seo_index_sync.py` docstring warns about running from a sandbox with a stale mount. The
filesystem the scripts read is authoritative — if you're operating on a copy, a bulk mutator
can act on stale content and write the result back over newer files. Confirm you're on the
real tree before running anything that writes.
