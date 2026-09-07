# Obsidian in this system — the architecture

Produced 2026-09-07 by a triple-fan workflow: seven research agents against primary
sources, each result attacked by an adversarial reviewer at max effort, the survivors
specced, then Fable at max effort synthesising the whole picture. 17 agents, ~2.0M tokens,
76 minutes.

**Five of the seven dimensions were rejected at the grounding stage as vault-polishing.**
That is the headline. The architecture below is mostly a set of refusals, and the refusals
are the deliverable.

> **Read the reporters, not this file.** Every number here has a half-life measured in hours
> in this system. Where a count appears it is stamped with the date it was measured and the
> instrument that measured it. `aria status`, `aria caps` and `aria doctor` outrank this
> document on every shared fact.

## Thesis

Obsidian should be the window and the keyboard, and nothing more — and that is the design, not a concession. The vault is a filesystem: 636 plain-markdown records and a TSV on one disk on one Mac, with one sanctioned writer (bin/aria) and one human input channel (`## My notes` in today's Daily note). That is already the integration Carlos asked for. The CLI reads and writes it; launchd runs the 03:17 nightly sweep and the :09 hourly queue against it; an hourly render (`bin/aria-cloud-render.sh`) already carries an opted-in, credential-guarded, sha-stamped slice of it to Drive, and a daily cloud Routine already applies that slice to cloud memory — I read today's render two minutes after it landed. The two dead Obsidian MCP servers were never gaps in that wire; they were attempts to build a second wire to the same files through a GUI. So Obsidian.app's whole job is to render the files when Carlos wants to read prose and to be the editor he types `## My notes` in. It stays at zero community plugins, because every plugin is unsandboxed code with the reach of his login and the first thing that would make the machine's writes race a GUI; the Obsidian CLI stays unregistered, because it needs the app running and adds nothing to `cat`; Sync stays unbought, because no account exists (zero mail from obsidian.md, ever) and the render bridge already does the job for $0. What should change is not Obsidian's role but two properties of the store: its epistemics — the vault must stop being allowed to assert a blocker without a probe that can say "no longer true", the only class of note that has ever cost money, and the very research chain that produced this brief carried one (the shop it calls empty has ten live listings in its RSS feed today) — and its reach, because the cloud's window into the vault is currently 4 records of 636 behind a 32 KB cap in a shell script. Nothing here earns revenue; the first move says so out loud instead of implying otherwise.

## The shape

# The vault is the store, bin/aria is the wire, Obsidian is the window

Everything below the top layer already exists and runs. The new parts are marked NEW; there are three of them and none is a plugin, a daemon, a port, a subscription, or a scheduled job.

```
                                   CARLOS  (the only pair of hands)
      reads:  chat · `aria status` (prints STANDING-DECISIONS at boot) · the Obsidian window, when he wants prose
      writes: ONLY under `## My notes` in Daily/YYYY-MM-DD.md   — his handwriting; the machine never touches it
      does alone: link a task to the Mac · approve a device-bound job · log in · pay · publish · delete
                │ W1 types in Obsidian                          ▲ W2 chat · machine sections in the Daily note ·
                ▼                                               │    at most one email a day, only to him, only on change
 ┌──────────────────────────────── MAC  carloss-mini ─────────────────────────────────────────────────────┐
 │  Obsidian.app = VIEWER + KEYBOARD. Core plugins only. 0 community plugins (measured 09-02, re-probed    │
 │     nightly from move 4). CLI not registered (probe). REST API :27124 -> 000 (probe). Sync: NO ACCOUNT   │
 │     (Gmail, 09-07). It sits BESIDE the wire, never on it: nothing the machine does needs it open.        │
 │              │ renders                                                                                    │
 │              ▼                                                                                            │
 │  /Users/aria/ARIA-Brain  == THE VAULT ==  the single authoritative copy. Plain files. No mirror.        │
 │     memory/ (636)   Daily/   Skills/   STANDING-DECISIONS.md   AUTONOMY.md   HANDOFF.md                  │
 │     state/capabilities.tsv  <- the ONLY place a blocker or a capability may live: dated, kind-tagged,    │
 │                                probe-backed (NEW columns, move 4). Prose points here; it never restates. │
 │              ▲ W3 read / write                                    ▲ stamps rows                          │
 │              │                                                    │                                      │
 │  bin/aria — the only writer (backup -> temp -> fsync -> replace -> read-back, NEW in move 5)            │
 │             and the read API: status · caps · inbox · find · read · doctor · handoff · backup           │
 │             doctor ──> bin/blocker_audit.py (NEW, move 4: metadata only, honest exit codes)             │
 │                        --run ──> bin/probes/*.sh  (exit 0 still blocked · 1 CLEARED · other = BROKEN)   │
 │              ▲                                                    ▲                                      │
 │  MAC AGENT ──┘  = any session that can see this disk:             │                                      │
 │     a desktop-app task linked to this Mac (desktop-commander: 393 calls / 1 failure on 09-02), or       │
 │     /Users/aria/.local/bin/claude launched INSIDE the vault, with ~/.claude/CLAUDE.md (move 6)          │
 │                                                                   │                                      │
 │  launchd (ALREADY RUNNING — the Mac's own scheduler):             │                                      │
 │     03:17 nightly sweep (claude -p) -> memory/state-nightly-digest.md  <── blocker_audit --run (move 4) │
 │     :09   hourly queue  bin/oneshot/                                                                     │
 │     hourly bin/aria-cloud-render.sh -> Drive  (opt-in `cloud: true` cargo + STANDING-DECISIONS,          │
 │            credential guard, per-record cap, .stamp = rendered-at · epoch · sha256-16 · bytes ·         │
 │            records · verified: cmp-ok).  Launchd cannot READ Drive (CloudStorage is behind Full Disk    │
 │            Access) and has a minimal PATH — every probe must carry explicit paths.                      │
 └──────────────┬──────────────────────────────────────────────────────────────▲──────────────────────────┘
                │ W4  ONE-WAY PROJECTION, hourly                                │ W5  cloud -> Mac:
                │     (generated document that says so; overwrite is safe;      │     INTERACTIVE ONLY —
                │     nothing is ever read back into the vault)                 │     "Link to this computer".
                ▼                                                               │     No scheduled path: measured
 ┌──────────────────────────── GOOGLE DRIVE  ARIA_BUS/ ───────────────────────┐ │     09-07 with a witness file.
 │  ARIA-CLOUD-MAP.md + ARIA-CLOUD-MAP.stamp  (today: 100 opted in, 4 published,│ │     Drive is an INBOX in this
 │  96 dropped by a 32 KB cap — the cap is the defect, not Drive).             │ │     direction, read only by a
 │  Move 7 widens it into stamped shards: per-kind memory, capabilities.tsv,   │ │     human-present Mac session.
 │  the nightly digest, `aria status`, a manifest.                             │ │
 │  HAZARD: this folder is owned by carlos@ariacapitalholdings.com — the       │ │
 │  Workspace account suspended for non-payment on 09-03 (owner act).          │ │
 └──────────────────────────────┬──────────────────────────────────────────────┘ │
                                │ read daily 14:30 UTC by the memory-merge Routine: refuses an absent render,
                                │ unescapes, asserts the first line, says so when the render is >2 days old
                                ▼                                                │
 ┌─────────────────────────────────── CLOUD ──────────────────────────────────────┴────────────────────────┐
 │  Interactive cloud sessions (claude.ai/code, unlinked Cowork): Gmail, Drive, Calendar, GitHub, Windsor, │
 │     PayPal, WebFetch, subagents, the aria-seo-site repo. They READ the bus. They never write the vault. │
 │  Routines: 13 recurring + one-shots — ALL cloud-only, NONE device-bound (measured: no bound_device on   │
 │     any of 16). memory-merge (bus -> /topics/aria-generated.md). morning-report is BLIND: its prompt    │
 │     reads Mac paths it cannot reach and is told to do nothing when it cannot — so it has never spoken. │
 │     nightly live-site monitor · weekly money check · PR/issue triage · dependency check · dashboard.   │
 │  Cloud memory: /topics/aria-generated.md = projection of the projection, generated, overwrite-safe;    │
 │     /topics/aria-map.md and /areas/* are hand-written and never clobbered by the merge.                │
 └──────────────────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                            │ W7 git push/pull by a human-present session; PR comments are a
                                            ▼    PUBLIC coordination bus (never credentials or account ids)
                              GITHUB  aria-capital/aria-seo-site  (CI gates, nightly live-site check)
```

## The wires, and which ones are dead

| wire | direction | mechanism | state |
|---|---|---|---|
| W1 | Carlos -> machine | `## My notes` in today's Daily note, read by `aria inbox` | live; his only inbound channel; keep it the only one |
| W2 | machine -> Carlos | chat; `aria status`; machine-owned sections appended to the Daily note; one email/day max, only on change | live |
| W3 | agent <-> vault | the filesystem, through `bin/aria` | live; Mac-only; the integration Carlos asked about |
| W4 | Mac -> cloud | hourly render + stamp into Drive; daily merge into cloud memory | live, 2 minutes old when read; lossy (4 of 100) — move 7 |
| W5 | cloud -> Mac | "Link to this computer" in the desktop app; Drive inbox read by a human-present Mac session | interactive only; no scheduled path (witness-file test 09-07) — move 8 is the one experiment |
| W6 | world -> vault | probes (curl, pgrep, explicit paths) stamping capabilities.tsv from the nightly; session instruments (Gmail, the built-in browser) stamping `session`-kind rows at boot | NEW — move 4 |
| W7 | Mac <-> GitHub | git by a human-present session; PR comments wake cloud sessions | live; public |
| dead | — | Obsidian REST API (000, no plugin) · obsidian-files MCP (client bug) · Obsidian Sync (no account) · Obsidian CLI (not registered; GUI-dependent; exit codes unverified) | recorded as probe-backed rows, not prose, so the record re-checks itself |

## Where each actor sits

- **Carlos** sits above everything with the only outward hands. His input is one heading in one file. His outputs from the machine are chat, one terminal command, and at most one email a day. He opens Obsidian when he wants to read prose; nothing depends on his doing so.
- **The vault** sits on one disk. It is the source; every other copy (Drive render, cloud memory, archives) is a projection that can be deleted and rebuilt from it, which is the test that it is not a mirror.
- **bin/aria** sits between every agent and the files. It is `safe_write.py` for the vault, and after move 5 it actually is (atomic replace + read-back on the call path — the lesson this repo paid for is that a safety module nothing calls is not a safety module).
- **Mac agents** sit on the Mac, in a session that can see the disk. They are the only agents that write the vault. They run the gate, the writer, the probes.
- **Cloud agents** sit on the other side of the bus. They own the repo, the connectors, research, and drafting. They read the vault's projection and never write the vault. Scheduled cloud runs are blind to the Mac by design; the architecture stops pretending otherwise and routes the Mac's findings TO them over W4 instead.
- **Obsidian.app** sits beside W1 and W2 as their human-facing surface. It is on no call path. Its measured absence of plugins, CLI registration, REST port and Sync account are each a probe-backed row, so the next session cannot inherit a stale claim about it in either direction.
- **launchd** is the Mac's scheduler and the cloud's Routines are the cloud's. Each runs on the side where its data lives. No new scheduler is added on either side.

## The seven contracts (each is held by a measurement, not a sentence)

1. **One writer.** Every vault write goes through `bin/aria`'s write function: backup, temp file, fsync, `os.replace`, read-back. Held by the `/dev/null`-symlink negative control (move 5).
2. **The Daily-note contract.** `## My notes` is human-only. The machine appends only its own dated sections, at most once a day, during the nightly/morning window when the editor is unlikely to hold the file, and reads back what it wrote. Held by the morning-report prompt's existing rule and by the read-back.
3. **Blockers are rows, not sentences.** A claim that something is blocked, unavailable, not signed in, or impossible lives in `state/capabilities.tsv` with a kind (`probe` = a command on the Mac settles it, 7-day TTL; `session` = an interactive session's instrument settles it — Gmail, the built-in browser — 14-day TTL; `owner` = only Carlos, 30-day TTL). `aria doctor` exits non-zero over an unprobed, expired, broken-probe, or dateless blocker, and it exits non-zero over an empty or column-less file — green over nothing is not green. Held by eleven negative controls (move 4).
4. **Projection, never mirror.** The vault renders to Drive; nothing renders back. The render is its own generated document, stamped with time and sha, credential-guarded, opt-in cargo, size-capped per record; the applying end refuses an absent render and reports the render's age. Already true; move 7 widens the cargo without changing the shape.
5. **Obsidian beside the wire.** No Obsidian process, plugin, port, CLI or subscription is on any call path. `obsidian create ... overwrite` is a RED line in AUTONOMY.md. Held by three probes and `grep -rn 'obsidian create' bin Skills` = 0.
6. **Two schedulers, no new ones.** Anything that must run unattended against the vault rides the existing nightly sweep or hourly queue on the Mac; anything that must run unattended against the internet or the connectors is a cloud Routine reading the bus. Standing decision 20 forbids a new cloud job that assumes the Mac; the observer count (~20 observers, 1 lifetime sale) forbids a new job of any kind without a measured reason.
7. **Every instrument carries a control and says UNKNOWN.** A probe that cannot run is BROKEN, never "still blocked"; a shop page that 403s is not "empty"; a run with Obsidian closed is UNKNOWN, not SURVIVED; a check that scanned zero files exits 3. The RSS probe written today has a real negative control (a nonexistent shop returns 404 and zero items) — the shop-page probe in the research chain would have been BROKEN forever.

## The moves, in dependency order

### 1. Say the true thing in chat, now, from this cloud session — no file, no plan, no handoff note. The words: "Nothing to install. Your vault is markdown on a disk, and bin/aria over those files IS the integration — it already runs nightly and hourly under launchd, and an hourly render already carries an opted-in slice of it to Drive and into cloud memory (today's render was two minutes old when I read it). The two dead Obsidian connections were second wires to the same files: one needed a plugin that was never installed in this vault, the other died in Claude's own client. Three things I measured today: your inbox has never received a mail from obsidian.md, so there is no Sync account to build on and the toggle in Settings is not a subscription; the Etsy shop is not empty — its public RSS shows 10 live listings, so the 'empty shop' blocker the research kept repeating is stale; and none of your 16 scheduled jobs is bound to the Mac, which is why the morning report has never spoken. None of what I'd do next earns money. I want one click from you — link the next task to the Mac — and one Mac session."

**Who:** agent-unattended · **Effort:** 5 minutes

**Why:** The ask is answered by an explanation, not a build, and it can be closed this minute. Every previous session that could not reach the Mac wrote a plan for a later session instead; that is the notes-read-later failure in miniature. This move also retires two stale beliefs the research chain itself carried (empty shop; Sync as a foundation) before anyone builds on them.

**Proves itself by:** It creates no artifact. If 'integrate Obsidian' is asked again after this, the answer failed. The three measured facts in it each cite an instrument (RSS item count with a 404 negative control; Gmail `from:obsidian.md` = 0 threads; trigger list with no bound_device field) so a later session can re-run them instead of trusting the sentence.

### 2. Link the next task to the Mac: Claude desktop app -> open the task -> "Link to this computer". Then, in that session, probe by exact name in one call (`ToolSearch select:mcp__remote-devices__plugin_desktop-commander_desktop-commander__start_process`) and proceed without asking.

**Who:** owner-only · **Effort:** 10 seconds

**Why:** Every vault-side move below queues behind a session that can see /Users/aria/ARIA-Brain. Scheduled cloud runs cannot reach the Mac (witness-file test, 09-07) and this session has no bridge. It is a ten-second act and it is the scarcest resource in the system, so the moves that follow are ordered to spend one Mac session, not several.

**Proves itself by:** `ls -d /Users/aria/ARIA-Brain` succeeds inside the session and the commander tool loads by exact name. If either fails, stop and say the one sentence again; do not write a handoff describing moves 3–8.

### 3. Measure before touching (Mac Step 0). Run and READ: `head -3 state/capabilities.tsv | cat -A` and the awk header dump (real column names and count); `head -1 bin/aria` and `grep -n 'open(' bin/aria` (language, and whether writes go through one function); `./bin/aria caps > /tmp/caps-before.txt; echo $?` and `./bin/aria doctor > /tmp/doctor-before.txt; echo $?`; which script writes memory/state-nightly-digest.md and where its exit paths are; `grep -n '32768\|cap' bin/aria-cloud-render.sh` and which Drive account the Mac's Drive client is signed into; `launchctl print gui/$(id -u)` PATH for the nightly job; `ls -l /usr/local/bin/obsidian; ls -d .obsidian/plugins`; `git -C ~/ARIA-Brain rev-parse --is-inside-work-tree`. STOP conditions: capabilities.tsv missing or zero data rows; bin/aria not python3 or writes scattered across several functions; no python3 on PATH.

**Who:** agent-unattended · **Effort:** 10 minutes

**Why:** Every filename, column name and function name in moves 4–7 is an assumption until this prints. The decay spec's Etsy probe was built on a blocker that was already false and a URL that 403s; ten minutes of measurement is what stops the next one. A STOP here is a valid, cheap outcome.

**Proves itself by:** The printed values decide the exact text of moves 4–7; nothing is written. `caps exit=0` and `doctor exit=0` are recorded so move 4 can prove it changed neither.

### 4. Build the blocker gate, scoped to blockers only, and wire it where it fires without anyone remembering. (a) Append four columns to the RIGHT of state/capabilities.tsv — blocker_kind (probe | session | owner), blocker_probe (vault-relative executable under bin/probes/, or the named instrument for session-kind e.g. `gmail:from:obsidian.md`, or ASK-CARLOS), blocker_verified (ISO date the blocker was last CONFIRMED — a fact about the past, never a prediction), blocker_verified_by. Then `diff /tmp/caps-before.txt <(./bin/aria caps)` must be empty or you revert. (b) bin/blocker_audit.py as specced in the decay chain, plus: the `session` kind with a 14-day TTL; and when EVERY probe-kind row is expired together, doctor prints 'the nightly runner has not run' rather than N separate expiries (a dead runner must announce itself, not look like N stale facts). (c) Probes, each with explicit paths because launchd's PATH is minimal: obsidian-rest-api.sh (curl 127.0.0.1:27124 -> 000 = still blocked), obsidian-community-plugins.sh (.obsidian/plugins absent = still blocked), obsidian-cli.sh (`[ -x /usr/local/bin/obsidian ] || command -v obsidian` -> absent = still blocked), and etsy-live-listings.sh reading https://www.etsy.com/shop/ClinicalvaultCo/rss — count `<item>`; >=1 = exit 1 (CLEARED), 0 items with HTTP 200 = exit 0, anything else = exit 3 (BROKEN). The shop PAGE 403s to curl from every vantage measured; the RSS returned 200 and 10 items today with a 404/0-item negative control on a nonexistent shop. (d) Seed rows: the three Obsidian probes (kind=probe); obsidian-sync-subscription-none (session, `gmail:from:obsidian.md`, verified 2026-09-07 by cloud-session: 0 threads ever); adsense-setup-incomplete (session, `gmail:from:adsense-noreply@google.com`, verified 2026-09-07: last mail 07-08 'Conecta tu sitio', nothing since); amazon-associates-not-enrolled (session, gmail, verified 2026-09-07: no enrolment mail exists). Do NOT seed etsy-shop-empty as a live row — see the acceptance test. (e) Wire `aria doctor` to call blocker_audit.py (metadata only, no probes) and propagate its exit code — if doctor currently swallows exit codes with `| tail` or `|| true`, fix that first. (f) Add `blocker_audit.py --run --runner nightly || true` to the deterministic part of the nightly sweep, ABOVE its exit paths, guarded so it cannot change the sweep's status, with its counts line written into state-nightly-digest.md. No new launch agent, no new Routine.

**Who:** agent-unattended · **Effort:** 3–4 hours, one Mac session

**Why:** Stale blockers are the only class of written fact that has ever cost this business money (55 days of an 'empty' shop behind a false 'Chrome not signed in'), and prose cannot hold them — the half-life is hours. `state/capabilities.tsv` + `aria caps` is the mechanism Carlos asked for on 08-20 ('figure out a way without me having to tell you every time'); this makes its rows self-verifying instead of self-reported. The `session` kind exists because most 'owner' blockers (AdSense, Associates, Sync) are settled by Gmail in thirty seconds — nagging Carlos for facts an agent can read is the failure the enumerate-before-can't rule names. Riding the existing nightly means it fires on the schedule that already exists, and its output lands in the digest that move 7 carries to the cloud.

**Proves itself by:** ACCEPTANCE WITH A REAL STALE BLOCKER: seed `etsy-shop-empty` (kind=probe, bin/probes/etsy-live-listings.sh) deliberately, run `./bin/blocker_audit.py --run`, and it MUST print CLEARED for that row, exit 2, and leave blocker_verified unstamped; then delete the row. Then the eleven negative controls from the decay chain on a COPY (`--tsv /tmp/nc.tsv`): missing file -> exit 3; empty file -> exit 3 '0 rows'; columns cut -> exit 3 naming them; kind=probe with empty probe -> exit 2; `--today 2027-01-01` -> exit 2 with 'window 7d' on probe rows and different windows per kind; dead probe path -> 'does not exist'; chmod -x -> 'is not executable'; probe scripts flip between exit 0 and 1 under a fake PATH / scratch vault (a constant is not a measurement); a probe that exits 7 under --run -> PROBE BROKEN, date unchanged; the real freshly-stamped file -> exit 0 with rows>0 and blockers>0; `aria doctor` exits non-zero when the audit does. Seven nights later doctor is quiet because the nightly stamped the rows — or red with the single line 'the nightly runner has not run', which is the gate diagnosing the failure it was built for.

### 5. Make bin/aria's writer the vault's safe_write, on the call path. Back up bin/aria, find the single write function, and make it: backup -> write to a temp file in the same directory -> fsync -> os.replace -> immediate read-back compared against the full intended text (`_verify_written`, raising `aria: write did not land: <path> (wrote N chars, read back M)`). For any append path, compute expected = prior + addition BEFORE writing; never build the expectation by reading the file back. Leave ARIA_VERIFY_DELAY unset. Skip the three-shape write-survival script entirely: with no Sync account there is no process that can revert a write, so it would print SURVIVED vacuously. The one race that does exist — Obsidian's editor holding the Daily note open — is covered by the Daily-note contract (append only, once a day, in the nightly/morning window) plus the read-back; verify it once by hand with today's note open in Obsidian.

**Who:** agent-unattended · **Effort:** 45 minutes

**Why:** This repo's defining failure was partial buffers left as live files by writers cut off mid-write, found a session later. A read-back catches a write that did not land; only an atomic replace prevents a kill mid-write from leaving a truncated live file. The wire chain proposed read-back alone; that is half of safe_write.py, and half was what let 980 files rot here.

**Proves itself by:** `grep -n '_verify_written(' bin/aria` returns the def AND at least one call site. Negative control: `ln -s /dev/null /tmp/nulltarget.md`, drive the write function at it, and it MUST raise 'write did not land ... read back 0'. Second control: kill -9 the process mid-write in a scratch copy and confirm the live file is unchanged and a temp file is what remains. If bin/aria is not python3 or has several write sites, stop and report — do not patch by guess.

### 6. Put the standing rules where every Mac session reads them, and add the one RED line. Write ~/.claude/CLAUDE.md on the Mac, inline, under 200 lines, no symlink, no @import that resolves outside the working directory (Cowork silently drops those): the vault is the source and every other copy is a projection; bin/aria is the only writer; blockers are rows — run `aria status`, `aria caps`, `aria doctor` and trust them over any sentence including these; the Daily-note contract; RED: never write under `## My notes`, never speak as him, never touch credential values or payments, never emit `obsidian create ... overwrite`. Add that last line to AUTONOMY.md's RED list too (back it up first). Keep numbers out of the file; point at the reporters.

**Who:** agent-unattended · **Effort:** 30 minutes

**Why:** CLAUDE.md is only read when a session starts inside the folder that holds it, and Mac sessions launch from wherever they launch; user scope loads everywhere. The rules that keep this architecture honest are otherwise re-derived per session, and a boot skill built from a stale copy has already made a session act on three refuted rules. `obsidian create overwrite` is documented by the vendor as 'overwrite if file exists' — destroying a file is its intended behaviour, so there is no bug to wait for, only a line to draw.

**Proves itself by:** `cd ~ && claude`, then `/context`: the file is listed under Memory files from a directory with NO project CLAUDE.md (the negative control — if it only appears when launched inside a project, the mechanism is not doing what the doc claims). `grep -n 'obsidian create' AUTONOMY.md` returns the RED line; `grep -rn 'obsidian create' bin Skills` returns zero hits, or the hits are reported rather than the rule claimed.

### 7. Widen the bus instead of buying Sync. On the Mac, change bin/aria-cloud-render.sh from one 32 KB file to stamped shards, each under the cap: a manifest (shard list + sha + rendered-at), STANDING-DECISIONS (as now), one shard per memory kind mirroring the `aria index` map, state/capabilities.tsv, memory/state-nightly-digest.md, and the text of `aria status`. Keep the credential guard, the per-record cap, the opt-in `cloud: true` rule, and the `verified: cmp-ok` comparison for every shard. Retarget the render folder to a Drive the personal Gmail owns if the Mac's Drive client can reach one (Step 0 measured which account it is signed into); if it cannot, this becomes an owner act and is said so. In the cloud, update the memory-merge Routine's prompt to read the manifest first, apply every shard, refuse when the manifest is absent, and report shard count and render age as it already does for the single file; and re-point the morning-report Routine at the digest shard in Drive instead of the Mac paths it has never been able to read. Announce both Routine edits in the report.

**Who:** agent-unattended · **Effort:** 2–3 hours on the Mac, 20 minutes of cloud prompt edits

**Why:** The render bridge is the merge-two-stores pattern done right — one author, a stamped one-way projection, a merge that refuses an absent render and says when it is stale — and it is lossy by two orders of magnitude only because of a cap constant in a shell script. Every cloud session and Routine currently sees 0.6% of the vault, which is why decisions get 're-litigated in good faith' and why 'the sweep has produced findings every night for weeks and nothing automated has ever read one' (standing decision 20). This closes both at $0 with no new mechanism, no subscription, no mirror, no credential in a container — the honest alternative to headless Sync. The bus's Drive folder belonging to an account suspended for non-payment is the one live hazard in W4 and belongs in the same change.

**Proves itself by:** Next merge run reports N shards applied and the render age; next morning-report run cites the digest's rendered-at date from the stamp (it has never cited anything before). Negative control: rename the manifest in Drive, fire the merge by hand, and it MUST refuse and say 'not applied' — an absent render must never overwrite a good file. A cloud session can read a named memory record from a shard that the old map dropped. KILL CONDITION, pre-registered: if after 14 days no session or Routine has cited anything beyond the standing decisions, revert to the single file and delete the shards; the bus was wide enough.

### 8. Run the one device-binding experiment, once. From the surface that offers it — the desktop app on the Mac; the cloud create_trigger schema has no such parameter, and standing decision 20 says binding must be declared at creation — create a Routine that runs on this computer with a single instruction: write `REACHED THE MAC` and a timestamp to /Users/aria/ARIA-Brain/state/trigger-reach-test.txt. Carlos approves it on the Mac. Fire it by hand. Read the file. Record the result as a `session`-kind capability row either way.

**Who:** agent-then-owner-clicks · **Effort:** 5 minutes of Carlos, 15 minutes of agent

**Why:** The harness exposes device-bound Routines (a trigger carrying bound_device, approved on that computer), the vault's own finding says one approval would fix the whole class of blind jobs, and a 09-02 note that the creation call was classifier-blocked was already contradicted on 09-07. It is the only candidate mechanism for scheduled work that can see the vault other than launchd, it costs five minutes, and it is settled by a witness file rather than an argument. It is ranked after move 7 because move 7 works whether or not this does.

**Proves itself by:** The witness file exists with a post-fire timestamp — the negative control was already run on 09-07 (an unbound run reported SUCCEEDED and wrote nothing). If it lands, the morning report may read the Mac directly and launchd keeps the deterministic parts; if it does not, move 7 is the permanent answer and no further scheduled job may assume the Mac (decision 20).

### 9. Optional, last: run bin/blocker_sweep.py once, report-only, and hand back only the counts line and the ten blocker-shaped sentences that touch money (Etsy, AdSense, Associates, Search Console, Gumroad, Workspace). No prose pass unless Carlos asks for one; if he does, it replaces sentences with a pointer to capabilities.tsv, never deletes paragraphs, and is backed up first.

**Who:** agent-unattended · **Effort:** 20 minutes

**Why:** The prose is where the next false blocker is hiding, but a 400-line triage list is another observer for the human, and his own skill says stop adding those. Ten lines he can act on beats four hundred he will not read.

**Proves itself by:** `files scanned=` is greater than 100 (the vault has 636 records; zero means the wrong root and exits 3 by design); `git status --short` or the backup diff shows only the new state/blocker-sweep-*.md — nothing else moved.

## Do not build

Each of these looked attractive and was refused for a measured reason.

- Any community plugin — Local REST API, Dataview, Tasks, Templater, Shell Commands, a kanban plugin. No reader of this vault is human, so a plugin adds nothing to `cat`; plugins run unsandboxed with the reach of his login (the April 2026 PHANTOMPULSE campaign shipped through Shell Commands + Hider, verified by two reviewers); Templater conflicts with Sync per Obsidian's own docs; and the zero-plugin property is exactly what makes shell writes to the vault safe to reason about. Spend it only for a measured reason, never to 'try something'.

- Reviving mcp-obsidian or obsidian-files. Both are second wires to files bin/aria already reads and writes. One needs a plugin that has never existed in this vault; the other died in Claude's own client. Re-testing obsidian-files is a thirty-second curiosity, not a foundation — and its death must not be written into the vault as settled fact either, which is how the false Etsy blocker started.

- Routing bin/aria's writes through the Obsidian CLI (`obsidian append` / `obsidian create`). It requires the app to be running (the first command launches a GUI as a side effect), its exit codes are an unverified third-party claim, `create ... overwrite` destroys files by documented design, and the append shape is the one the #52493 report says was reverted. The filesystem write it would replace is the shape that survived.

- Obsidian Sync ($4/user/month billed annually, $5 monthly) and the headless Sync client. No account exists — zero mail from obsidian.md in the owner's inbox, ever, the same evidentiary standard that settled Amazon Associates. The headless client needs `ob login --email --password --mfa` credentials persisted in an ephemeral container or pasted into chat every session: both refusals. A full-vault replica is mirror #10, carrying the file with plaintext bank digits. And standing decision 0a makes the first milestone cutting recurring spend, not adding a line item. The render bridge already does this job for $0.

- Catalyst ($25 one-time) to reach 1.14.0's Bases kanban. 1.14.0 is Catalyst-only early access (changelog tag `catalyst`; latest public desktop is 1.13.7). It would buy a view over notes nobody opens, on a business with $14 lifetime revenue.

- A phone capture path — Siri/Shortcuts, an iCloud queue, Working Copy, a second `inbox/INBOX.md`. Any phone-side copy is a mirror, price-agnostic; the vault already writes 636 records with no evidence a thought was ever lost; and two inboxes is the drift problem in miniature next to `## My notes`.

- A Cockpit.md, Bases dashboards, or any `.base` view over memory/. Roughly twenty observers already exist against one lifetime sale; the owner's own unblock-dont-instrument skill adjudicates this shape. An empty Base cannot distinguish 'nothing needs attention' from 'the folder name is wrong' — a silent false negative in the reassuring direction. `task-todo:""` is undocumented. Nobody looks through the window.

- Frontmatter `verified:` stamps on 636 memory records. A self-reported freshness stamp written by the same machine that writes the record is laundering, the same move as re-recording damage as a new baseline floor. It would mean 636 verification acts nobody performs. Blockers-only is the scope; capabilities.tsv is the file.

- A cloud vault replica via git, headless sync, or a bigger Drive archive read path. It scales the defining failure — stale snapshots read faster, from more places, with the authority of a fresh pull — and adds a second staleness axis. Cloud sessions own the repo, the connectors and research; they read the vault's projection and never need the vault.

- A new launch agent, a new cloud Routine, an `aria doctor wire` subcommand, or a new memory note about Obsidian integration. The nightly sweep, the hourly queue, `aria caps` and capabilities.tsv are the mechanisms and they already self-stale. Standing decision 20 forbids a new cloud job that assumes it can see the Mac; the observer count forbids a new job of any kind without a measured reason; and a prose note about integration is the thing that rots in three hours.

- The three-shape write-survival script (overwrite / read-modify-write / append). It measures a Sync race on a machine with no Sync account; it would print SURVIVED vacuously and a later session would read that as a measured property of the vault. Build it only if a Sync subscription ever appears.

- A Drive-to-vault return path, or any two-way sync. That is the mirror that drifted nine copies. The render is a projection; the cloud reads it; nothing comes back except through a human-present Mac session that chooses to.

- An Etsy 'publish the first listing' task. The 'shop empty for 55 days' blocker in this research chain is stale: the public RSS shows 10 live listings today (13 measured from the signed-in dashboard on 09-05). What remains on Etsy is a spend decision (ads — decision 3 says paid placement is the barrier) and a pre-registered kill test (300 clicks, 0 orders), both his. Do not build a probe on the shop page either: it 403s from every vantage measured; the RSS is the instrument.

- Anything on the 'Neuron' privacy-first AI toolkit. It appears on neither Obsidian's roadmap nor its changelog; three independent fetches of the primary sources found nothing. Treat it as fabricated by 2026's AI-written Obsidian listicles.

## Only Carlos can do these

- Link the next task to the Mac — Claude desktop app -> open the task -> "Link to this computer". Every vault-side move (3–9) waits on this; it is ten seconds and the scarcest resource in the system.

- Confirm the Sync screen, ten seconds, no purchase — Obsidian -> Settings -> Sync. Expect it to say a subscription is required. If it shows an active plan with a renewal date, say so: that would contradict Gmail (zero mail from obsidian.md ever) and would mean a second email address the machine cannot see.

- Approve the device-bound job, only if move 8 is wanted — in the Claude desktop app ON the Mac, the Routine created to run on this computer asks for approval there; approve it once. Read the exact labels on screen; do not trust this note for menu text. A witness file settles whether it worked.

- Finish AdSense — the two screens Google itself named in its mail, both still open since July: adsense.google.com -> "Completa tu perfil" (payments profile and address; phone verification when prompted) -> "Conecta tu sitio" (Sites -> add aria-capital.github.io -> request review). Never apply under a second identity; the account holding pub-5576001602612111 exists. Honest expected value until traffic exists: about $0 — the verified property showed 10 impressions and 0 clicks in the last 28 days — so it is cheap, not urgent.

- Amazon Associates, only if the 72 `ariacapital-20` links should ever earn — affiliate-program.amazon.com -> Sign up -> enter the site URL -> complete the tax interview. No enrolment mail has ever arrived, so today they earn nothing.

- Move the plaintext bank routing and account digits out of `project_aria_company.md` into his password manager, then tell a session to redact the file. Owner-only because it is a credential value; until then the vault, the six-hourly archive and any render that ever opts that file in all carry it.

- Delete or move the twelve Chrome credential-store profiles (Gumroad, Amazon KDP: Cookies, Login Data, Local State) sitting in the suspended Workspace Drive under `ARIA_EMERGENCY_20260725/` and `Other computers/My PC/Desktop/ARIA_BACKUP_KIT/`. A session can list the exact paths (the 09-07 finding already does); deletion is his line.

- Decide the Google Workspace account (`carlos@ariacapitalholdings.com`, suspended for non-payment on 2026-09-03) — Admin console -> Billing: pay, or migrate. It hosts the domain's mail (MX is smtp.google.com, so mail to that address is accepted and then invisible) AND the `ARIA_BUS` Drive folder the render writes into. If migrating, tell a Mac session which Drive the render should target so move 7 can re-point it.

- Etsy Ads, a spend — Shop Manager -> Marketing -> Etsy Ads -> set a daily budget. Standing decision 3 says paid placement, not ranking, is the barrier; decision 4 pre-registers the kill test (300 clicks and 0 orders -> stop selling PDFs). A session may draft the budget arithmetic and the click count to watch; the money is his.

- The Obsidian commercial-licence question — obsidian.md/pricing lists $50/user/year for organisations using Obsidian for work. Whether a one-person LLC running a vault as business infrastructure is in scope is his to decide or to ask Obsidian; no session should assume either way.

## The single biggest unlock

Blockers become measurements. If only one thing gets done, it is move 4: `aria doctor` refuses to be green over an unprobed, expired, or broken-probe blocker; the probes run inside the nightly sweep that already exists; and their counts line lands in the digest that the existing bus can carry to every cloud session. This is the single mechanism that changes what EVERY future session believes, on both sides of the split, without anyone remembering to run anything. It is the exact counter-move to the failure that has recurred five times — a snapshot read as current truth — applied to the only class of snapshot that has ever cost money: the 55-day 'Chrome is not signed in to Etsy' blocker would have expired at day 7 as a probe row or day 30 as an owner row instead of standing unchallenged, and the reframe it forces ('state the measurable outcome, not the believed cause') is what would have made it a probe in the first place. It proved its worth before it was built: applying its discipline to this very research chain found that the 'empty shop' blocker the reviewers repeated is false (RSS: 10 live listings, with a 404 negative control) and that the shop-page probe they specified would have been BROKEN forever (403). It costs one Mac session, adds no scheduler, no plugin, no port, no subscription, and it is the piece that makes `state/capabilities.tsv` — the mechanism Carlos himself asked for on 08-20 — worth trusting at boot. Precondition: one click from Carlos (link the task to the Mac).

## The honest case that this whole architecture is a mistake

Kept at full length and last, because it is the strongest section in the document and
the one most likely to be right.

The strongest case against all of this is that it is more of the same thing, and the system's own records say so. Roughly twenty observers already exist — eleven live cloud Routines, a nightly sweep, an hourly queue, seven `aria` reporting verbs, the repo's nightly live-site check — against one lifetime sale of $14. The vault's own standing decisions, written this week, say 'zero further build hours until a stranger fills the form', 'NO FIFTH ROUTE', and 'the next thing recorded here is a measurement, not a plan'; and its own decision 10 says 'the vault is 600 records deep and reading it feels like working — that is the trap.' A blocker gate instruments the machine's beliefs, not money. Its counterfactual on the one costly incident is 'day 7 or 30 instead of day 55' — and only if the nightly keeps running and someone reads the digest, which decision 20 says nothing automated has ever done. Widening the bus ships MORE of a record store that the owner's own file calls a trap into the cloud, faster, with the authority of a fresh stamp: more re-litigation fuel, not less. The Mac session is the scarcest resource in the whole system and moves 3–7 spend one on TSV columns, a writer patch and a render script, exactly the pattern the brief names — manufacturing engineering because the human acts (an AdSense form, a spend decision, a suspended Workspace bill, bank digits in a note) are his and unglamorous. And the gate carries its own failure mode: probe rows expire in seven days, so if the nightly hook is not wired or breaks, `aria doctor` goes red within a week and stays red, and a permanently red gate is the one everyone learns to ignore — the truncation bug's mechanism, rebuilt. Chat and a terminal already do most of what this architecture describes: `aria status` prints the standing decisions, `aria caps` already stales at 14 days, Gmail answers any account question in thirty seconds, and an interactive session at boot can re-check a blocker faster than a probe can be written. If that case is right, the correct plan is: say move 1, do nothing else in the vault, and spend every Mac session on the owner's list. What would prove it right, pre-registered: thirty days after move 4, if `blocker_audit.py --run` has stamped rows fewer than twenty times (a working nightly gives ~30), or no session has cited a capabilities row it did not itself write, or the memory-merge Routine has never reported a shard beyond the standing decisions — delete the gate and the shards, keep the writer patch and the RED line (those cost nothing to keep), and let chat and a terminal be the architecture.

## Independent verification of the load-bearing correction

Fable's architecture rests in part on a claim that contradicts a blocker this system has
been acting on: that the Etsy shop is not empty. Because that claim is both consequential
and convenient, it was re-measured from this session rather than taken on trust, using the
same instrument and the same negative control.

```
ClinicalvaultCo                          -> HTTP 200, <item> count = 10
aria-no-such-shop-negative-control-xyz   -> HTTP 404, <item> count = 0
```

**Confirmed. The shop has ten live listings.** The negative control is what makes the 200
mean something: it proves the instrument reports absence when a shop genuinely does not
exist, so ten items is a measurement rather than a hopeful default. The returned titles are
real products — the report-sheet line, the CRNA worksheet, the interview workbook, the
$39 leadership binder.

Two cautions that survive the confirmation:

- **This does not close the open retitle ask.** The feed shows the pre-edit title, but the
  shop's own ask file records that this RSS served a stale title once before, and it
  explicitly forbids closing or keeping an ask open based on the feed. The live listing page
  is the authority for that question. Absence of the new title here is evidence of nothing.
- **Do not build a probe on the Etsy shop *page*.** It returns 403 to a plain fetch from
  every vantage measured. A probe built on it would report BROKEN forever, which is a
  check that can never pass — the failure mode this repo already documents. The RSS is the
  instrument.

The general point is the one the architecture is built around: a blocker that no instrument
can contradict will outlive the condition it describes. This one was false, it was repeated
by several agents in the chain that produced this document, and it took one HTTP request
with a control to settle.
