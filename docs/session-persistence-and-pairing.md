# Making a session survive the chat, and reach the Mac

Two questions, researched 2026-09-07 against Anthropic's own documentation and measured
against the live account:

1. How does every session get the full context without anyone remembering to launch from
   the right folder?
2. Is there a way to run something on the Mac, on a schedule, that outlives the chat that
   created it?

Both have clean answers. One of them is "you already built this."

## 1. Every session gets the context — `~/.claude/CLAUDE.md`

`CLAUDE.md` files load in this order, broadest first, and **all discovered files are
concatenated rather than overriding each other**:

| Scope | Location | Loaded when |
|---|---|---|
| Managed policy | `/Library/Application Support/ClaudeCode/CLAUDE.md` (macOS) | every session on the machine |
| **User** | **`~/.claude/CLAUDE.md`** | **every session, every project, every directory** |
| Project | `./CLAUDE.md` or `./.claude/CLAUDE.md` | when launched at or below that directory |
| Local | `./CLAUDE.local.md` | same, gitignored |

So the "always launch from the right folder" problem is solved by not needing to: **user
scope loads regardless of the working directory.** Project files are found by walking from
the working directory up to the filesystem root, which is why launching from `~` finds
nothing — there is no `CLAUDE.md` on that path.

### The caveat that would silently bite

`~/.claude/CLAUDE.md` can pull in other files with `@path` imports, and for ordinary
Claude Code those are trusted without a prompt because they are your own files. **In Cowork
sessions on the desktop this is different**: Claude Code

- **skips any import in a user-scope file that resolves outside the session's working
  directory**, and loads the rest of the file, and
- **skips a `~/.claude/CLAUDE.md` that is itself a symlink or hard link**, and a symlinked
  `~/.claude/rules/` pointing outside the working directory.

So `@~/ARIA-Brain/STANDING-DECISIONS.md` inside `~/.claude/CLAUDE.md` works in the CLI and
**silently loads nothing in Cowork**. Nothing errors; the content is simply absent. Given
that this project has already been bitten by a boot file that was a stale copy, an import
that quietly evaporates on one surface is exactly the wrong mechanism.

**Therefore: put the content inline in `~/.claude/CLAUDE.md`, and do not symlink that
file.** Keep it under ~200 lines — the docs are explicit that longer files reduce
adherence, and anything over 4 MiB is skipped entirely.

Two other routes worth knowing:

- `~/.claude/rules/*.md` — user-level rules, loaded for every project. Rules with `paths:`
  frontmatter load only when Claude touches matching files, which is a way to carry a lot
  of guidance without spending context on it every session.
- `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude --add-dir ~/ARIA-Brain` — loads
  the vault's own `CLAUDE.md`, `.claude/rules/*.md` and `CLAUDE.local.md` from any launch
  directory. Useful, but it depends on remembering a flag, which is the failure mode being
  fixed. Prefer user scope.

**How to verify, with a negative control:** run `/context` in a session and read the list
under **Memory files**. A file that is not listed there did not load, whatever the
filesystem says. The negative control is to launch from a directory with no project file
(`cd ~ && claude`) and confirm the user-scope file still appears — if it does not, the
mechanism is not doing what this document claims.

## 2. The commando already exists

The thing being asked for — something that runs on the Mac, on a schedule, with full
access, outliving the chat — is `claude -p` under `launchd`. It is documented, supported,
and **already running on this machine**: the nightly job and the hourly queue are exactly
this shape.

`claude -p "<prompt>"` runs Claude Code non-interactively. What matters for unattended use:

| Flag | Why it matters here |
|---|---|
| `--permission-mode auto` | a classifier reviews actions instead of a human |
| `--permission-prompts none` | **for jobs where nobody can answer.** Anything that would prompt is denied, Claude is told nobody can approve and not to retry, and the run continues instead of hanging. Requires **v2.1.259+** |
| `--output-format json` | result plus `session_id`, and `total_cost_usd` per invocation |
| `--json-schema '{…}'` | forces structured output into a `structured_output` field |
| `--resume "<session_id>"` | continues a specific conversation, **from any directory** (v2.1.223+) |
| `--append-system-prompt` | adds instructions without replacing the default prompt |

Three properties that matter more than the flag list:

- **Exit codes are honest.** `claude -p` exits 0 on success and non-zero on failure, so a
  wrapper can branch on status. (Contrast the Obsidian CLI, which always exits 0 — see
  `obsidian-integration-research.md`. Two CLIs in the same pipeline with opposite
  error-reporting conventions is a real trap.)
- **Do not pass `--bare` here.** It skips hooks, skills, subagents, plugins, MCP servers,
  auto memory *and* `CLAUDE.md`. It is the right default for CI reproducibility and the
  wrong one for a job whose whole purpose is to act with the vault's context. It also
  never reads OAuth credentials, so it needs an API key.
- **A sleeping Mac does not lose the run.** `launchd` fires the job when the machine wakes.

`total_cost_usd` deserves its own line. Every scheduled run can report what it cost, in
JSON, without opening a dashboard. For a project whose stated first milestone is the
machine paying for itself, that is the one number worth wiring, and it is one `jq` away:

```bash
claude -p "…" --output-format json | jq -r '.total_cost_usd'
```

(The docs note it is a client-side estimate and can differ from the actual bill.)

## 3. What does not work, measured rather than assumed

**A cloud session cannot reach the Mac on a schedule.** Re-measured today rather than
trusted from notes, and the notes turned out to be stale in one direction and right in the
other:

- **`persistent_session_id` now works.** An older note recorded it as *"not enabled for
  this organization."* That is no longer true — two live triggers are bound to specific
  sessions and firing. **But it binds cloud session → cloud session.** A local Mac session
  is identified by a plain UUID, which the trigger API rejects as an invalid tagged ID.
- **There is still no self-hosted runner.** Both environments on the account are
  `anthropic_cloud`.
- Two existing triggers already record this limit in their own names — one reports itself
  as blind for want of a device binding, another is switched off because it needs the Mac
  and cloud runs cannot reach it. The constraint was discovered before and written down in
  the only place that survives: the name of the thing it broke.

So the direction that works is **Mac → out**, not **cloud → Mac**. A `launchd` job on the
Mac has everything a cloud session lacks; a cloud session cannot borrow it.

## 4. The part that argues against building anything

The mechanism is not the gap. **There are already about a dozen active scheduled jobs on
this account** — dashboards, triage, digests, monitors, weekly checks — against a business
with roughly $14 of lifetime revenue.

The vault's own standing decisions say this plainly, and a recent handoff says it again:
piling more scheduled watchers onto a queue that is not draining is the named failure mode,
not the fix. So the honest answer to "can you pair yourself to the Mac on a schedule" is:

> Yes, and you have already done it a dozen times. The reason it does not feel like it is
> working is not that a fourteenth job is missing.

The one durable, zero-cost thing that genuinely makes every future session better is item 1
above: put the standing context in `~/.claude/CLAUDE.md`, inline, on the Mac. That is a
file, not a job. It cannot fail silently at 3am, it costs nothing per month, and it is read
by every session on every surface that reads user scope.

## Sources

- <https://code.claude.com/docs/en/memory>
- <https://code.claude.com/docs/en/headless>
- Measured against the live account: environment list, trigger list, and this session's own
  tool availability.
