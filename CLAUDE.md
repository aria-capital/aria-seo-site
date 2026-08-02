# CLAUDE.md — working notes for this repo

Read this before changing anything. It records what broke here, why, and the rules that
keep it from breaking again. Most of it was learned the expensive way.

## Start here

**Run `python repo_state.py` first. Believe it over this file.**

This document has been substantially wrong at the start of three consecutive sessions —
not through carelessness, but because it is written as a snapshot and read as current
truth, and every fix widens the gap. One session opened with a Known-issues list where
most items were already closed and burned an hour re-deriving that by hand. The next
session closed the sitemap item, which made the list stale again the same day.
`repo_state.py` prints the underlying numbers in two seconds; it exists so nobody pays
that hour again.

**The engineering backlog is essentially closed.** The corpus is clean (1,461 articles,
zero damaged, empty baseline), both gates are strict and run on push, PR and nightly, and
298 tests cover it. There is no pile of broken things left to find.

**What remains is not engineering, and this is the part worth internalising:**

- **No revenue channel works, and no code change makes one work.** AdSense is not approved
  and there are zero `<ins>` ad units on the site; Amazon Associates enrolment is
  unconfirmed; zero affiliate programs are approved; Google has indexed nothing. Every one
  of those is an account action only the owner can take.
- The remaining site-shape questions — the 852 homepage orphan cards, the three brand
  identities — are curation decisions, not defects.

So: **do not go looking for code to write.** If a session opens with no specific ask, the
useful move is to say plainly what is blocked on the owner and stop, not to manufacture a
refactor. A green test suite is not progress toward revenue, and this repo has already
spent more sessions polishing the machine than the machine has ever earned.

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

**Repairs** — `fix_truncated_articles.py`, `restore_newsletter_blocks.py`,
`restore_truncated_footers.py`, `restore_truncated_blocks.py`, `close_unclosed_blocks.py`,
`fix_index_html.py`. One-time fixes for a specific class of damage. All are idempotent and
have run to completion; they are kept so the repair is reviewable and re-runnable, not
because there is work left for them.

**Generators** — `build_seo_index.py`, `build_article_hub.py`, `generate_sitemap.py`.
These create files from scratch.

**Gates** — `check_article_corpus.py` (CI) and `tests/` (276 tests, pytest).

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

**The floor is now zero.** `tests/corpus_baseline.json` is empty: all 1,461 articles are
clean. "No worse than baseline" and "not damaged at all" are therefore the same statement,
and the regression gate has become a cleanliness gate without a line of it changing.

Two consequences worth keeping in mind:
- `--update-baseline` now **refuses** to record a file that got worse. That was the one way
  a green gate could quietly stop meaning anything — re-record the damage as the new floor
  and every later regression is laundered through it. `--allow-new-damage` overrides it if
  damage ever genuinely has to be grandfathered again.
- Don't reintroduce grandfathering casually. The empty baseline is the asset; a single
  careless entry gives back the property that took three repair passes to earn.

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

- **no `model` key, deliberately.** The main loop runs the default (strongest) model. An
  earlier revision pinned `model: "fable"` here; that was a misreading of the owner's intent
  and was reverted. Do not re-add it — see "Model policy" below.
- `ultracode: true` and `effortLevel: "xhigh"` — maximum reasoning effort with standing
  dynamic-workflow orchestration, so substantive tasks get fanned out and adversarially
  verified without the owner typing the keyword
- `workflowSizeGuideline: "large"` and `skipWorkflowUsageWarning: true` — workflows run
  without a size cap fight or an approval prompt
- **no `permissions.defaultMode` key** — see the next section. The owner does run without
  approval prompts; that setting just must not live in a *public* file.

**Do not remove these to "be safe".** They are a deliberate, repeated decision by the repo
owner, made after finding the prompt volume unworkable. If a future session finds them
absent, it is because the session is on a branch that predates them, not because they were
reconsidered.

### Where `bypassPermissions` lives, and why not here

The owner runs with approval prompts off. That is not in question and must not be narrowed.
But it is configured in **`.claude/settings.local.json`**, which is untracked and gitignored,
never in the committed `.claude/settings.json`. Two reasons, one of each kind:

- **Ethical.** This repo is public. A committed `defaultMode` disables approval prompts for
  anyone who clones it, on their machine, without them ever choosing that. The owner's
  preference is his to make for his machines; it is not his to make for strangers.
- **Empirical — it was never working here anyway.** Claude Code *refuses* bypass permission
  modes under root: `--dangerously-skip-permissions cannot be used with root/sudo privileges
  for security reasons`. Cloud containers run as root, so the committed line had no effect in
  any cloud session. Verified by clean-room test on CLI 2.1.220, comparing a gated write
  across user scope, project scope, and the CLI flag — all three blocked identically under
  root, while the same write succeeded when permitted. It only ever mattered on a normal-user
  machine, which is exactly where the local file now carries it.

`localSettings` outranks `projectSettings` in the merge order, so the local file is a strict
upgrade: same effect where it matters, zero publication.

**On a fresh clone (a new Mac, a new machine), the local file does not exist** — it is
gitignored, so it does not travel. Recreate it once per machine:

```bash
mkdir -p .claude && cat > .claude/settings.local.json <<'EOF'
{"permissions": {"defaultMode": "bypassPermissions"}, "skipDangerousModePermissionPrompt": true}
EOF
```

Held by `tests/test_claude_settings.py`, which fails if `defaultMode` reappears in the
committed file, if a `model` key is pinned, if `ultracode`/`effortLevel` are dropped, or if
the local file stops being ignored by **this repo's own** `.gitignore`. That last one is not
pedantry: the cloud container ignores the path via a machine-level global gitignore that a
Mac clone does not have, so without the in-repo rule the file is committable from the Mac and
the leak returns by accident.

### Model policy — stated by the owner, 2026-08-01

> "When you use Fable make sure it's at Max, in the newest model. But you are the default
> selection, you always Ultracode. Saves so much time, and money when we work smart."

Clarified by the owner the same night: **"whichever is the highest model and thinking for
each."** So the rule is stated by role, not by model name — model names go stale, the rule
should not.

1. **Every role runs the highest model available to it, at the highest thinking tier that
   role supports.** Do not settle for a cheaper tier to save time or tokens; the owner's
   position is that working smart saves both, and under-powering a hard task wastes more of
   each than it saves.
2. **Main loop: do not pin `model` in settings.** The default selection resolves to the
   strongest model; pinning can only weaken it. Its thinking ceiling is
   `effortLevel: "xhigh"` — `"max"` is not a valid settings value, so xhigh IS the maximum
   here and is already set.
3. **Subagents: highest model, `effort: 'max'`.** The Workflow tool's per-agent `effort`
   does accept `max`, and that is the tier to use. At the time of writing the heavy-analysis
   model is Fable — so `model: 'fable', effort: 'max'` — but if a stronger one exists when
   you read this, use that instead. The instruction is "highest", not "Fable".
4. **Ultracode is always on.** Reach for the Workflow tool on substantive work rather than
   grinding serially — that is the time-saving the owner is describing.
5. **Working smart is the point, not maximum spend.** Do not fan out a workflow for a
   one-line config change or a trivial edit; that burns the budget the orchestration is
   meant to protect. Reserve fan-out for work with real breadth — investigation across many
   files, adversarial verification, competing designs. Highest-tier on the *right* work, not
   on everything.

This division earned its keep in the session that established it: Fable at max produced the
truncation-repair specification and the restructure plan, both of which caught defects the
main loop had missed — while the main loop kept context, made the judgement calls, and
carried the work to merge.

These were verified empirically against the installed CLI (v2.1.220), not inferred from the
schema — the schema's "session-scoped" wording is misleading:

1. **`ultracode: true` in project settings genuinely works.** Confirmed in a clean-room test:
   an isolated config dir with a project `.claude/settings.json` of `{"ultracode": true}`
   makes `/effort current` report `ultracode (xhigh + dynamic workflow orchestration)`, where
   the same harness with `{}` reports `auto (currently high)`. The schema's note that
   "interactive toggles never persist it" is about toggles, not settings files. Settings are
   merged across `userSettings, projectSettings, localSettings, flagSettings, policySettings`.
2. **`"max"` is not a valid `effortLevel`.** The settings enum is `low | medium | high |
   xhigh`, so `xhigh` is the ceiling for the main session. (`max` exists only as a per-agent
   `effort` inside the Workflow tool, where it is used for the heaviest verification passes.)
3. **Project scope is the right home, and user scope would be useless here.** `~/.claude`
   lives inside the ephemeral container and is rebuilt every boot, so a user-scope write
   reaches zero future sessions. Only the committed project file survives.
4. **Known risk — `flagSettings` outranks project settings.** Remote sessions are launched
   with `--settings /root/.claude/launcher-settings.json`, which the launcher regenerates on
   every boot and which sits above project scope in precedence. An explicit
   `"ultracode": false` there would silently defeat the project setting with no warning.
   Today that file carries no effort keys, so nothing is being overridden. A bare
   `effortLevel` there does *not* defeat ultracode (the ultracode check short-circuits
   first); only an explicit `ultracode:false` or a CLI `--effort` flag does.
5. `skipWorkflowUsageWarning` is not read from project scope at all — only user, local, flag
   and policy. It is kept in the file anyway because it is harmless, and it is redundant
   while ultracode is on: the ultracode gate short-circuits before the warning check runs.

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

**Lead with where the capability exists, not with what you cannot do.** The owner asked
perhaps six times for Claude to drive his browser and click through AdSense. Each time he got
an accurate explanation of why a cloud container cannot reach his Mac. All of it was true and
none of it helped, and he had bought a Mac partly on the belief that it would work. The
correct first answer was one line: *install Claude Code on the Mac, it drives Chrome there.*
That took under ten minutes once actually attempted. Hours went into explaining a limitation
instead of routing around it. When someone asks for something you cannot do, spend the effort
finding the surface where it IS possible before spending any on the explanation.

**Setup facts learned the same way, so nobody re-derives them:**
- The install script is at `claude.ai/install.sh`, not `claude.com/install.sh` — the latter 404s.
- Installing the Chrome extension is not enough. It must be SIGNED IN to the same account, or
  `list_connected_browsers` returns empty and every browser call fails with "not connected".
- Settings are read at startup only. Writing `~/.claude/settings.json` mid-session changes
  nothing until Claude Code is restarted — verify with `/effort current` afterwards.
- `CLAUDE.md` is only loaded when Claude starts INSIDE the folder containing it. A session
  launched from the home directory knows none of this file. Clone the repo locally and launch
  from within it, or the local session is blind while the cloud one is not.
- The desktop app is the right recommendation for a non-technical owner: same capability as the
  terminal CLI, but a real window. "It looks like a command tab" is a fair complaint.

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

**A green gate only means what it measures.** `html_severity()` counted `<div>` and nothing
else, so both gates scored `dmca-policy.html` and `nurse-real-estate-investing.html` as
perfectly clean while each carried a `<footer>` truncated mid-word. Sixteen more files were
hiding the same way behind unclosed `<main>`, `<article>`, `<ol>` and `<table>` tags. Nothing
was wrong with the gate's logic — it was answering a narrower question than the one everyone
was reading it as. When a check reports clean, ask what it does not look at; the damage that
survives is exactly the damage that falls outside the metric.

**Measure the rule against the healthy corpus before running it on the broken one.** Every
repair rule in `close_unclosed_blocks.py` was first checked against the 1,334 files that were
already fine, where the right answer is known: the leaf rule predicted the true position of
the closing tag for 2,347 of 2,355 blocks, and the 8 misses became the refusal condition
rather than a bug found later. A rule with a measured error rate can be given a matching
guard; a rule that merely looks correct cannot.

**These notes go stale faster than anyone expects — measure before you trust them.** Three
sessions running, the Known-issues section was substantially wrong on arrival, and each
time the wrongness pointed the same way: work listed as open was already done. The failure
is structural, not sloppy — a snapshot read as current truth. `repo_state.py` is the fix;
run it before planning anything. And when you close an item, fix the note in the same
commit, because the next session cannot tell a stale bullet from a live one.

**The measured half-life of a number in this file is about three hours.** Not a figure of
speech. PR #6 merged at 09:58 carrying the bullet *"the sitemap question is unresolved…
picking the 934 is the owner's call"*. PR #8 merged at 13:19 and curated the sitemap to
940. The note was true when written, true when reviewed, true when merged, and false
**3h21m later** — and it then sat there misinforming the next two sessions. Nobody was
careless; several sessions land work in this repo on the same day, and prose cannot track
that.

So write Known-issues bullets to survive it: **state the hazard in prose and let
`repo_state.py` supply the count.** "Four scripts can write the sitemap and three would
revert the curation" stays true until someone fixes it; "the sitemap has 1,461 URLs" is
false the moment anyone touches it. A sentence with a number in it has an expiry date, so
either point at the reporter or accept that you are writing something with a deadline.

**Prove a repair script reproduces the tree, don't just prove it ran.** After the
141-file block repair, the check that actually settled it was: `git archive HEAD` into a
scratch dir, copy the scripts in, run them in order, `diff -rq` against the working tree.
Zero differing files means the committed scripts genuinely produce the committed result —
so a reviewer can re-derive 148 changed files instead of reading them, and a later session
can re-run the repair without wondering whether the tree drifted from the code. Cheap, and
much stronger than "it exited 0".

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

## Closed since the test-coverage work

Do not re-litigate these; they were measured, not assumed. Each is now held by a test.

- **The HTML corpus is clean.** Zero damaged files out of 1,461, and
  `tests/corpus_baseline.json` is empty. The last three passes closed 141 files carrying
  unclosed `<div>`/`<main>`/`<article>`/`<ol>` tags, restored 3 truncated `<footer>` blocks,
  and put back prose in 7 articles that had been cut mid-sentence.
- **`index.html` is repaired** and `check_site_integrity.py` is a required CI gate.
- **AdSense pub ID**: `ads.txt` and all 1,460 pages now agree on `pub-5576001602612111`.
  (Still no `<ins class="adsbygoogle">` unit anywhere, so nothing can serve either way.)
- **One Amazon tag**: 72 links, all `ariacapital-20`. `aria-affiliate-20` is gone.
- **`?via=aria` placeholders**: none left.
- **Canonicals and disclaimers**: every article has `rel="canonical"`; every clinical page
  carries disclaimer language.
- **Only `build_curated_sitemap.py` can write the sitemap.** Four scripts called
  `safe_write_sitemap()` and three of them would have replaced the curated file with a
  full-corpus dump, silently, with every existing check still green. The write path now
  requires a keyword-only `curated=True` that only the curator passes, so the other three
  fail loudly at the moment of damage; `check_sitemap_curated.py` is the CI backstop for
  writes that never reach `safe_write` at all. It asserts that no article below the
  curator's quality floor is advertised — an invariant that survives content growth and
  batch widening, where a byte- or set-comparison would go red on both.
- **`generate_sitemap.read_base_url()`** no longer falls back to a dead host — it refuses.
- **`seo_index_sync.linked_in_index()`** now matches any local href, so `privacy_policy.html`
  stops reading as an orphan on every run.

## Known issues

- **`seo_index_sync.py` would add 852 orphan cards** to `index.html` on its next run.
  Whether those articles should be linked from the homepage at all is a curation decision
  for the owner. (Its sitemap write is now blocked — see below — but its index write is
  not, and that is the part still needing a decision.)
- **`generate_sitemap.build()` writes `sitemap.xml` and `robots.txt` as a side effect**, and
  its `<lastmod>` comes from file mtime — so merely *calling* it to inspect the output
  rewrites the live sitemap with today's dates on every article you happen to have touched.
  This bit during the block-repair work and had to be reverted. It has no `--dry-run`.
  Use `read_base_url()` if you only want to check the host.
- **Three articles are still cut off mid-word**, and no revision in git history has the rest:
  `best-icu-nursing-books-2026` ("…rather than a study gui"),
  `new-grad-nurse-financial-survival-guide` ("…Employer match captured. Loans"),
  `roth-ira-for-nurses-complete-guide` ("…inside the account (don't le").
  Their block tags are closed, so the pages render correctly and the damage is confined to
  one trailing sentence each. Finishing those sentences means writing content, which is a
  decision for the owner, not a repair. Everything recoverable was recovered — see
  `restore_truncated_blocks.py`.
- **1,255 `.fuse_hidden*` files are committed** — orphans from unclean FUSE unmounts, not
  byte-identical to any live article. Junk, but tracked, so removal is the owner's call.
- **Three brand identities**: `_config.yml` says "Money Psychology", footers say "ICU
  Notebook" (1,460 articles), the org is "aria-capital". "ARIA Capital Holdings LLC"
  appears in 61 pages — that one is *correct* and must not be tidied away; it is the
  publishing entity required by standing priority 2.
- **The published contact address is inconsistent, and one form is a personal first name.**
  `legal@ariacapitalholdings.com` on 47 pages, `info@` on 1, and
  `carlos@ariacapitalholdings.com` on 27 (26 of which also carry the street address).
  Raised with the owner; not changed, because redirecting a live business contact path is
  his call and mail to a role alias that does not exist would simply vanish.

## Commands

```bash
python repo_state.py                             # RUN FIRST — measured state; trust over these notes
python -m pytest -q                              # 298 tests
python check_article_corpus.py                   # CI gate: zero damaged HTML, no exceptions
python check_article_corpus.py --update-baseline # after repairing files; refuses new damage
python check_site_integrity.py                   # index.html + sitemap.xml; required in CI
python fix_cookie_banner.py --dry-run            # every mutator has a dry run
```

`pytest` is not preinstalled in a fresh cloud container: `pip install -r requirements-dev.txt`
first. And check the exit code, never `| tail` — see "Check exit codes directly" below.

## Environment note

The `seo_index_sync.py` docstring warns about running from a sandbox with a stale mount. The
filesystem the scripts read is authoritative — if you're operating on a copy, a bulk mutator
can act on stale content and write the result back over newer files. Confirm you're on the
real tree before running anything that writes.
