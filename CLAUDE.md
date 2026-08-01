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

## Session defaults — the owner never wants to set these by hand

`.claude/settings.json` in this repo turns on, at session start:

- `model: "fable"` — the owner's chosen default model
- `ultracode: true` and `effortLevel: "xhigh"` — maximum reasoning effort with standing
  dynamic-workflow orchestration, so substantive tasks get fanned out and adversarially
  verified without the owner typing the keyword
- `workflowSizeGuideline: "large"` and `skipWorkflowUsageWarning: true` — workflows run
  without a size cap fight or an approval prompt
- `permissions.defaultMode: "bypassPermissions"` — no approval prompts. The owner asked
  for this repeatedly and explicitly; do not quietly narrow it.

**Do not remove these to "be safe".** They are a deliberate, repeated decision by the repo
owner, made after finding the prompt volume unworkable. If a future session finds them
absent, it is because the session is on a branch that predates them, not because they were
reconsidered.

Three caveats worth knowing, all unverified at the time of writing:

1. The settings schema describes `ultracode` as session-scoped and says interactive toggles
   never persist it. Setting it in a settings file *should* apply at startup, since settings
   are read then — but if a session starts without ultracode behaviour, that is the reason,
   and `effortLevel: "xhigh"` still applies independently.
2. **`"max"` is not a valid `effortLevel`.** The settings enum is `low | medium | high |
   xhigh`, so `xhigh` is the ceiling for the main session. (`max` exists only as a per-agent
   `effort` inside the Workflow tool, where it is used for the heaviest verification passes.)
3. **`ultracode` requires an xhigh-capable model.** If `model: "fable"` turns out not to
   support xhigh, ultracode will not engage and the session silently falls back. If a session
   feels shallower than expected, test by removing the `model` line — that is the one-line
   revert, and it is the first thing to try before assuming the other settings failed.

## Standing priorities for this project

The owner's goal is a business that earns without putting him at risk. In practice that
resolves to a small number of rules that should outrank tidiness, cleverness, or speed:

1. **Never publish a claim the site cannot support.** Especially professional review or
   authorship of clinical content. This is the top rule, and it has already been violated
   twice (commit c795a01, then the 64 pages this work removed).
2. **Publish as the entity, never as a named individual or a claimed credential.** The site
   is published by ARIA Capital Holdings LLC; keep it that way. Do not re-add personal
   bylines, names, or professional credentials to any page — the reasons are on file with
   the owner and are not restated here, because this repository is public.
3. **Every clinical page carries a disclaimer.** Enforced by a test. A disclaimer does not
   make wrong content safe, so this is a floor, not a solution.
4. **Monetization identities must match the ones the platforms authorize.** One AdSense
   publisher (matching ads.txt), one Amazon tag. A second identity earns nothing and looks
   like inventory laundering.
5. **Prefer removing a false statement over adding a qualifying one.** Removing an untrue
   claim cannot create new exposure; adding new copy is a business decision that belongs to
   the owner.

What is explicitly NOT in scope for automated work, because no amount of code review can
settle it: whether the entity is in good standing, tax treatment, whether the clinical
content is factually correct, and whether the site's overall model is sound. Those need a
lawyer, an accountant, and a clinician respectively. Say so plainly rather than implying
that a green test suite is legal safety — it is not.

## Lessons paid for in mistakes

Each of these cost real work to learn. They are here so the next session does not re-buy them.

**Verify the mechanism exists before optimizing which variant is correct.** Hours went into
determining which AdSense publisher ID was authoritative — provenance, git archaeology, a
1,460-page rewrite, then a full revert. The whole question was moot: there is not a single
`<ins class="adsbygoogle">` ad unit anywhere in 1,477 files. Every page carries only the
loader, and a loader with no slots renders nothing. The argument was about the label on an
empty box. Ask "does this work at all?" before "which version of this is right?"

**ads.txt is fetched from the ROOT of the host, never a project subpath.**
`aria-capital.github.io/ads.txt` is authoritative and lives in the *aria-capital.github.io*
repo, which is a separate repository. The `ads.txt` in THIS repo sits at
`/aria-seo-site/ads.txt`, no crawler reads it, and it must never be used as evidence of
which account is real. Reasoning from it produced a confident, wrong, 1,460-page change.
Fetch both files before touching a publisher ID.

**Do not excise what can be restored.** The truncation repair discarded damaged trailing
blocks wholesale. That was right for promo boilerplate and wrong for the newsletter block —
171 email-capture forms, the site's mailing list, deleted as if they were noise. They turned
out to be byte-exact prefixes of two canonical templates and were fully recoverable. Before
discarding a damaged block, check whether the healthy corpus or git history can complete it.

**Check exit codes directly.** `pytest -q | tail -3` always exits 0, because the pipeline
reports `tail`'s status. A failing test was committed and pushed behind that mask, and CI
caught what the local run had hidden. Never gate a commit on a piped command.

**Confident inference is still inference.** The AdSense ID was chosen by git provenance and
was wrong. The Amazon tag `ariacapital-20` was chosen the same way and is still UNVERIFIED —
nobody has read the Associates console. Reasoning from repo evidence is the right method when
no better source exists, but label it as inference and say what would settle it.

**The site is one limb of a larger system.** `company_auditor.py`, `president.py`,
`trade_journal.py`, `../.env.aria`, a parent `CLAUDE.md`, and a recurring "Session Brief" all
live outside this repo and are not visible from a session scoped to it. Ask for what is
missing rather than inferring the whole from the part.

## The ARIA vault is readable from a cloud session — via Google Drive

This took most of a session to discover, so it is written down. A session running in a
cloud container has no path to the owner's laptop, but the **Google Drive connector reaches
the ARIA vault directly**. Use `mcp__Google_Drive__search_files` then
`download_file_content` (returns base64 — decode it).

Start here:
- `project_aria_company.md` — what ARIA is, the department model, the North Star goal stack
- `ARIA Company Health Dashboard.md` — which departments actually run
- `aria-machine-roles.md`, `aria-how-to-stop-things-safely.md` — operational runbooks
- folder `AI Context` = `1S-2SwBgCVLZ5iUQpXghyFIJeJPMl5pa_`; `projects` = `1z2_X426wtQCJ9BqzG2h-2BGIA6VD5gn9`

### What the vault settles about money — read this before optimizing anything

Sourced from the vault and cross-checked against the repo. **No revenue channel currently
works.** Fixing the site does not change that; only the owner's account actions do.

- **AdSense is not approved, and may never have been applied for.** `adsense_tracker.json`
  (07-30) says PENDING with a dashboard URL containing the literal string `pub-PENDING`,
  while `carlos_actions.json` still lists "Apply to Google AdSense" as an open to-do. The
  2026-07-22 org rename also means the site must be re-added as a new property. There are
  zero `<ins class="adsbygoogle">` units in the corpus — only the loader. **No ad can serve.**
- **Amazon Associates enrolment probably never happened.** `ariacapital-20` is the intended
  tag and all 72 links carry it, but "Sign up for Amazon Associates" is still open in
  `carlos_actions.json` (07-30). If unenrolled, every one of those links earns nothing.
- **Zero affiliate programs are approved.** `ARIA_AFFILIATE_LINKS.txt` — the file meant to
  hold real referral URLs — is blank. This is why 8 fabricated `?via=aria` links existed and
  were removed; do not re-add a referral link until a program has actually approved.
- **Gumroad lifetime revenue is $14.00, one sale**, on a product that shipped broken
  (duplicate PDFs, iOS black-screen), with a refund owed and apparently never issued. Six
  product slugs were deleted 2026-07-15 — any link to them 404s.
- **Google has not indexed a single article.** `SEO_TRAFFIC_AUDIT.md` (07-24). The
  mechanical cause (robots/sitemap/canonicals aimed at the dead pre-rename host) is fixed
  and live, but indexing since then is unmeasured.

**The plan of record is `plan-30-days-20260728.md`** (Fable, human-reviewed): make the real
Gumroad products and the best ~700 clinical articles reachable and honest; **build nothing
new**. Its explicit warning matters here — *do not submit all 1,461 URLs for indexing*: the
site matches three of Google's four scaled-content-abuse triggers, and a mass submission is
manual-action bait. Use the curated 934-URL sitemap it describes. (Note: the 379 articles
that plan quarantines are all still live and serving.)

**ARIA itself is unrun scaffolding, not an operating company.** `intent_router` has a
lifetime route count of **0** — the front door has never been used. Department health scores
40/100 with most departments never having run. Treat any machine-generated ARIA dashboard
number as unreliable; several contradict each other on the same day.

Facts already established from it (dated 2026-07-29, treat as possibly stale):
- **AdSense is awaiting Google review — not approved.** No ads can serve regardless of
  which publisher ID is on the pages. This is why there are zero ad units.
- **ARIA revenue is $0.** Gumroad's products published 2026-07-08 with no sales; the
  owner's own diagnosis is a traffic gap, not a product gap.
- Only 102 of 217 registered departments have ever run, and company state is ~30 days
  stale. `adsense_monitor`, `affiliate_tracker`, `gumroad_monitor_dept` and
  `seo_performance_monitor` are registered but have **never run** — they would have caught
  most of what this branch had to repair by hand.
- The GitHub org was renamed 2026-07-22 (`Carlostrujilloglz1991` -> `aria-capital`); the
  old username is dead for Pages, which is why stale canonicals pointed at a dead host.

**Security:** `project_aria_company.md` contains live bank routing/account digits in
plaintext. Flagged to the owner; do not echo credential values from vault files into
commits, PR bodies, or chat.

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
