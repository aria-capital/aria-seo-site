# Obsidian integration — measured facts

Primary-source research, 2026-09-07. Everything here was fetched from Obsidian's own
documentation (`obsidian.md/roadmap`, `obsidian.md/changelog`, `obsidian.md/help/*`,
`obsidian.md/pricing`), not from blogs. Where a claim came from a third party it is
labelled as such.

**Why this file exists separately from the conclusions:** the conclusions are a judgement
call and will age. These are version numbers and command names, which age differently and
can be re-checked against a URL. Keep the two apart so a stale opinion cannot borrow
credibility from a fresh fact.

## Versions and what actually shipped

> **Corrected 2026-09-07, same day, by an adversarial review of this file.** The first
> version of this section said "Obsidian desktop is at 1.14.0, released 2026-09-02" and
> listed 1.14.0's features as shipped. That is wrong, and wrong in the direction that would
> have produced a plan nobody could run. The correction is kept visible rather than quietly
> edited, because how the wrong answer was reached is worth more than the answer.

**The latest PUBLIC desktop release is 1.13.7** (2026-08-12); the latest public mobile is
1.13.8 (2026-08-20). **1.14.0 (2026-09-02) is Catalyst-only early access** — the changelog
tags each release either `public` or `catalyst`, and 1.14.0 carries `catalyst`.

Early access is gated: *"Early access versions are only available to users with a Catalyst
license."* **Catalyst is a separate $25 one-time purchase, and a Sync subscription does not
include it.**

So everything 1.14.0 introduced — the **kanban layout for Bases**, collapsible groups in
table/cards/list, colour highlights, Temml replacing MathJax, RTL support — **is not
generally available** and must not be designed against. This is consistent with the roadmap
still listing "Kanban view for Bases" as *active* rather than launched; early access is not
shipped.

The general lesson, which is the one this repo keeps re-buying: **a version number on a
changelog is not the same as a version you can install.** Read the tag next to it.

Shipped features that matter to an automated system, with the release that carried them.
All of the following are `public` — available without Catalyst:

| Feature | Shipped | Version |
|---|---|---|
| **Obsidian CLI** | Feb 2026 | 1.12 (early access), GA in 1.12.4 |
| **Headless client for Sync** | Feb 2026 | 1.12 |
| Bases search | Feb 2026 | 1.12 |
| Template logic for Web Clipper | Feb 2026 | 1.12 |
| Siri and Shortcuts integration | Jan 2026 | 1.11 |
| Mobile widgets | Jan 2026 | 1.11 |
| Keychain | Jan 2026 | 1.11 |
| Obsidian Reader | Mar 2026 | — |
| iOS Share Sheet | Jul 2026 | 1.13 |
| Settings search | Jul 2026 | 1.13 |
| Airtable import | Aug 2026 | — |

Not in that table, because it is **not public**: kanban layout for Bases and collapsible
groups, Sep 2026, 1.14.0, **Catalyst early access only**.

On the roadmap and **not shipped**: Kanban view for Bases (active), Obsidian for Work
(active), Open individual Markdown files (active); Background Sync on mobile, Bases support
for Publish, Calendar view for Bases, Canvas support for Publish, Multiplayer, PDF
annotation, Sort search results by relevance (all planned).

### One claim to not build on

Several 2026 SEO blogs describe a privacy-first Obsidian AI toolkit codenamed **"Neuron"**,
with local small models and optional API models. It appears on **neither** the official
roadmap **nor** the changelog. Treat it as unverified and probably fabricated — 2026 has a
lot of AI-generated Obsidian listicles that invent features. Do not plan around it.

## The CLI — the significant finding

Obsidian ships a first-party command line interface. It needs **no community plugin**.

- Enable at **Settings → General → Command line interface**, then follow the registration
  prompt. Requires the 1.12+ installer; docs state 1.12.7+.
- **This survives the Catalyst correction above.** The CLI shipped `public` in 1.12.4, and
  the current public release (1.13.7) is well past the 1.12.7 floor — so the CLI is
  available without buying anything. It is the one major finding here that costs nothing
  and is gated on nothing.
- On macOS it installs a symlink at `/usr/local/bin/obsidian`.
- **Obsidian must be running.** If it is not, the first command launches it.
- Syntax: `obsidian [vault=<name>] <command> [key=value ...]`. Quote values containing
  spaces. Bare `obsidian` opens a TUI with autocomplete and `Ctrl+R` history search.
- Roughly 100+ commands. It communicates with the running app over IPC.

Command surface, grouped (this grouping is from a third-party guide cross-checked against
the official docs page, which confirms the categories but does not enumerate every command):

- **Daily notes** — `daily`, `daily:path`, `daily:read`, `daily:append`, `daily:prepend`
- **Files** — `create` (with `content=` or `template=`), `read`, `append`, `prepend`,
  `move` (updates wikilinks), `delete`
- **Search** — `search`, `search:context`, `backlinks`, `links`, `orphans`
- **Properties** — `property:set` (`type=text|list|number|checkbox|date`), `property:read`,
  `property:remove`, `aliases`
- **Tasks and tags** — `tasks` (`todo|done|daily|all`), `task`, `tags`
- **Templates and Bases** — `templates`, `template:insert`, **`base:query`** (returns JSON,
  CSV, TSV, MD or paths), `base:create`
- **Execution** — `command` (run any Obsidian command by id), `eval` (arbitrary JS with full
  `app` access)
- **Other** — `history`, `history:restore`, `diff`, `outline` (`format=tree|md|json`),
  `plugins`, `plugin:enable`, `plugin:disable`

### The gotcha that will bite, and has bitten this system before

> **Exit codes are always 0, even on failure.** Errors must be detected by parsing the
> command's output text.

This is precisely the failure mode already recorded in this repo's `CLAUDE.md` — a piped
command reporting the pipe's exit status let a failing test get committed. Any wrapper
around `obsidian` that gates on `$?` is a check that cannot fail. If the CLI is wired into
anything, the wrapper must parse output and must have a negative-control test proving it
reports failure when the underlying call failed.

### Why `base:query` is more interesting than it looks

`base:query` returns **JSON**. That makes Bases a queryable interface over vault
frontmatter, not merely a UI. A `.base` file becomes a saved query that both a human reads
as a table in the app and a script reads as structured data — one definition, two consumers,
no second source of truth to drift.

## Headless Sync — real, documented, and paid

`obsidian.md/help/sync/headless`:

- A command-line sync client, explicitly for "CI pipelines, agents, and automated
  workflows". Same encryption as desktop, including end-to-end.
- Prebuilt binaries for Windows (x64/ARM64/IA32), macOS (x64/ARM64), and **Linux**. Linux
  works but lacks native birthtime preservation.
- Install: `npm install -g obsidian-headless` (needs Node/npm). Currently **open beta**.
- Auth: `ob login`, then `ob sync-setup --vault "<name>"`. Requires an **active Obsidian
  Sync subscription**.
- **Stated limitation:** it cannot run at the same time as desktop Sync *on the same
  device* — data conflict risk. A different machine is fine.
- Docs recommend backing up before first use.

**Why this matters here:** a cloud session has no route to the Mac unless a human links the
task to the computer. A headless client on a machine a cloud session *can* reach would hold
a live replica of the vault. That is the only documented, first-party mechanism that
addresses the split.

**Why it is not free:** it needs a paid Sync subscription, and the "same device" limitation
means it is a *second* machine's client, not a replacement for the Mac's. Whether to buy is
the owner's call, not an agent's — it is a spend.

## Prices, as published

| Product | Annual | Monthly | Notes |
|---|---|---|---|
| Sync | $4/user/mo billed annually | $5/user/mo | E2E encryption, version history |
| Publish | $8/site/mo billed annually | $10/site/mo | Public site from vault notes |
| Catalyst | $25 one-time | — | Early access to betas |
| Commercial licence | $50/user/yr | — | For organisations using Obsidian for work |

The pricing page does not state storage limits, device counts, or vault counts.

Note the commercial-licence line. A one-person LLC running a vault as business
infrastructure is plausibly in scope. That is a question for the owner, not a thing to
assume either way.

## `.base` file format

A `.base` file is YAML with five top-level sections: `filters`, `formulas`, `properties`,
`summaries`, `views`. By default a base includes **every file in the vault** until filters
narrow it.

```yaml
filters:
  and:
    - file.inFolder("memory")
    - 'status != "retired"'

formulas:
  age_days: '(now() - verified).format("D")'

properties:
  verified:
    displayName: Last verified
  formula.age_days:
    displayName: Days since checked

views:
  - type: table
    name: Stale first
    filters:
      and:
        - 'formula.age_days > 14'
    order:
      - file.name
      - verified
      - formula.age_days
    summaries:
      formula.age_days: Max
```

Mechanics worth knowing:

- Filters accept `and` / `or` / `not`, nested recursively. Statements are either comparisons
  (`status != "done"`) or function calls (`file.hasTag("x")`, `file.inFolder("y")`,
  `file.hasLink("z")`).
- Global filters and view filters concatenate with AND.
- Property references: `note.price` (the `note.` prefix is optional), `file.size` /
  `file.ext` / `file.name`, `formula.<name>`.
- Formulas are stored as YAML strings; their output type follows the underlying data. No
  circular references.
- Summaries operate on a `values` collection — built-ins include Average, Min, Max, Sum,
  Range, Median, Stddev for numbers; Earliest/Latest/Range for dates; Checked/Unchecked for
  booleans; Empty/Filled/Unique for anything.
- View types: `table`, `cards`, `list`, `map`, and as of 1.14 `kanban`. Views take `name`,
  `limit`, `groupBy`, `filters`, `order`, `summaries`.

## What the cloud can actually see of the vault — measured 2026-09-07

Measured from a cloud session with no device bridge, using only the Google Drive connector.
This matters because it defines what a cloud session can know without a human linking a Mac.

**A render bridge exists and is current.** `bin/aria-cloud-render.sh` writes `ARIA-CLOUD-MAP.md`
into Drive. Today's render was stamped 16:14 UTC — under two hours old when read. So the
bridge is alive, not theoretical.

**But it is lossy by two orders of magnitude, and it says so itself.** Today's header:

> 94 record(s) marked `cloud: true` · 4 published · 0 withheld by the credential guard ·
> **90 dropped to fit the 32768-byte cloud cap** · vault holds 629 records total.

So of 629 records, 94 are opted in, and **4 arrive**. Individual records are additionally cut
at a 2,400-byte per-record cap, mid-sentence. The render is admirably honest about this — it
names the drop count and lists what it left behind — but a cloud session reading it is seeing
roughly 0.6% of the vault.

**The full archive is pushed to Drive and cannot be read from the cloud.** Vault archives
(~25.7 MB, `aria-archive-YYYYMMDD-HHMM.tar.gz`) land in Drive roughly every six hours with a
`MANIFEST.sha256` beside them; the newest was 16:12 UTC today. Attempting to download one
through the Drive connector fails:

```
File too large for download, over limit of 10 MB.
```

That is worth stating plainly: **the backup path proves the data left the Mac, but does not
let anyone in the cloud read it.** Those are different properties, and the archive only has
the first. A cloud session's real read surface is the 32 KB render, not the 25 MB archive.

### The diagnosis the vault has already made about itself

This is the most important input to any Obsidian design here, and it did not come from
research — it came from the vault's own `STANDING-DECISIONS.md`:

> 571 records, findings written as orphans nothing links to, and — until 2026-09-06 —
> `INDEX.md` at 82 KB, too large to load into a session at all. **Decisions that cannot be
> reached get re-litigated by the next session, which then contradicts them in good faith.
> That is not a memory problem, it is a retrieval problem.**

And, in the same file:

> **The vault is 600 records deep and reading it feels like working — that is the trap.**
> A record is a claim about the past. The world is the instrument.

Two consequences for anything built on top of this vault:

1. **Capture is not the bottleneck.** 629 records exist. The system is extremely good at
   writing things down and bad at getting them back. Any proposal that adds a new way to
   record things is treating the symptom the vault has already ruled out.
2. **Nothing here captures automatically.** Every record exists because a session chose to
   write it, and a session that ends between a result and its record loses the result. So a
   mechanism that only works when someone remembers to run it is already the failure mode.

### The constraint that disqualifies the most attractive option

The headless Sync client is the cleanest technical answer to the cloud/Mac split. It should
still probably be refused, and the reason is not technical.

This project's stated first financial milestone is **reducing recurring spend** — the machine
paying for itself before it earns anything. A new subscription, however cheap, moves in the
opposite direction of the only currently live goal. `$4/month` is small; `a new recurring line
item added while trying to cut recurring line items` is not a small thing to explain.

The free alternative already exists and is running: the render bridge. It is not lossy because
Drive is bad, it is lossy because of **a 32 KB cap in a shell script**. Raising or paginating
that cap costs nothing per month and recovers most of what the paid option would buy.

That is the shape of the honest recommendation here — fix the free thing that is already
running before buying the thing that would replace it.

## Sources

- <https://obsidian.md/roadmap/>
- <https://obsidian.md/changelog/>
- <https://obsidian.md/help/cli>
- <https://obsidian.md/help/sync/headless>
- <https://obsidian.md/help/bases/syntax>
- <https://obsidian.md/pricing>
- Third-party, cross-checked where noted:
  <https://www.dsebastien.net/the-complete-guide-to-the-obsidian-cli-everything-you-can-do-from-the-terminal/>
