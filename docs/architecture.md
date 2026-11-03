# Architecture (for contributors)

About 3,000 lines of Python in `src/olmcp/`, standard library plus PyMuPDF, PyYAML, RapidFuzz and (optional) the
MCP SDK. For the reasoning behind decisions and the options that were rejected, read [design.md](design.md).

## Principles

1. **Git is the database.** Comments, replies, patches and decisions are plain files in the repository.
2. **A connector, not a policy.** The tool gives agents capabilities and honours what the researcher chose
   (comment tags, decisions). How an agent works is its instructions' job, not the tool's.
3. **The diff is the authority.** What changed is computed from git, never taken from the agent's description.
4. **Protocol in code, not hope.** What can be enforced (atomic edits, path confinement, one comment per commit)
   is enforced in the tools; the rest is instruction text.
5. **Optional parts degrade quietly.** No TeX, no `olcli`, no `latexdiff`: the rest still works, and the tool
   says what is switched off.
6. **Nothing hosted, no secrets handled.** Credentials stay with git and `olcli`; this tool never reads them.

## The shape of it

```
              ┌─────────── cli.py (olmcp ...) ───────────┐
              │                                           │
   mcp_server.py ──► review_tools.py (PaperTools)   local.py (pull / push)
   (MCP tools)            │                              │
                          ├── store.py (comment files)   ├── sync.py / markers.py   %% markers
                          ├── modes.py                   ├── overleaf.py            native comments via olcli
                          ├── markers.py                 ├── apply.py               decisions → cherry-pick
                          └── local.py (branches)        ├── redline.py             latexdiff + annotations
                                                         ├── changelog.py
                                                         └── gitutil.py (every git call)
```

Everything that touches git goes through `gitutil.py`; `review_tools.PaperTools` is the one place that
implements agent-facing operations, used by both the MCP server and the `address` CLI command.

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing and output for every `olmcp` command |
| `config.py` | `.olmcp.yml` (and the legacy name), main-file and engine detection, the `Config` dataclass |
| `store.py` | One JSON file per comment under `review/comments/`; merging two edits of one file |
| `markers.py`, `sync.py` | Parse `%% @agent:` markers; reconcile them with the store |
| `overleaf.py` | Native comments through `olcli`: parse its JSON, import threads, post replies, derive decisions from threads |
| `modes.py` | `direct` / `suggest`, tag parsing, writing the default mode |
| `review_tools.py` | `PaperTools`: list/show comments, read files, `address_comment`, `reply_to_comment`, `set_mode` |
| `mcp_server.py` | Registers `PaperTools` as MCP tools (needs the `mcp` extra); translates errors for the agent |
| `local.py` | `pull` and `push`: fetch/rebase, import, apply decisions, refresh the redline, publish |
| `redline.py` | Flatten, `latexdiff`, attribute changes to commits, annotate every change, decision lines |
| `apply.py` | Apply decisions: cherry-pick accepted commits, drop rejected, reopen comments, roll back on conflict |
| `textdiff.py` | Inline word diff used by the redline and the Overleaf thread replies |
| `build.py`, `anchor.py` | Optional rendering (page images, text boxes); quote matching |
| `changelog.py` | `review/CHANGELOG.md` from `Resolves:` commit trailers |
| `init.py`, `templates/` | What `olmcp init` writes (config, `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, slash command) |
| `ci.py` | What the GitHub workflow runs (CI mode) |
| `gitutil.py` | Thin `git` wrapper, trailer parsing, comment-file conflict auto-merge |

## The comment file

`review/comments/C-NNNN.json`, written with sorted keys so diffs stay small:

```json
{
  "schema": 1, "id": "C-0003", "kind": "comment", "status": "open",
  "created": "2026-11-03T09:00:00Z", "author": "human:you@example.com",
  "body": "[suggest] make this less absolute",
  "mode": "suggest",
  "anchor": {"quote": "always outperforms the baselines", "page": 3,
             "source": {"file": "sections/results.tex", "line": 12, "confidence": 1.0}},
  "origin": {"type": "overleaf", "external_id": "overleaf:<thread>", "thread_id": "<thread>",
             "doc_id": "<doc>", "messages_seen": ["m1"], "resolve_pushed": false},
  "thread": [{"author": "agent", "at": "...", "body": "Softened the claim.",
              "mode": "suggest", "edits": [{"file": "...", "old": "...", "new": "..."}]}],
  "resolution": null
}
```

- `status`: `open`, `addressed`, `resolved`, `wontfix` (`stale` is reserved, never set automatically).
- `origin.type` is `marker` (a `%% @agent:` line, identified by a hash of file and text) or `overleaf`.
- `mode` is present only when the researcher tagged the comment.
- A reply records the `mode` and `edits` of the change it describes; the Overleaf thread message is built from them.

## Data flow

**`olmcp pull`**: fetch, fast-forward or rebase the default branch (never a merge commit) → sync `%%` markers →
import Overleaf threads (new comments, follow-ups, closures, deletions) → derive decisions from threads → apply
decisions (typed lines in `redline.tex` win) → rebase the round branch onto your edits if the paper changed →
refresh the redline → report.

**`address_comment`**: pick the mode (tag beats argument beats default) → put the repo on the right branch
(`direct`: default branch; `suggest`: the local `agent/round-N`, first rebased onto direct edits made meanwhile)
→ validate every edit (`old` matches once, path allowed) → write files, remove the marker, record the reply →
one commit with `Resolves: C-NNNN`; any failure resets and removes a branch it just created.

**`olmcp push`**: post missing agent replies to Overleaf threads (idempotent: a reply is posted only if no
message starts with its text) → refresh the redline and change log → push the default branch (retry once after a
rebase if you pushed meanwhile).

## Git model

- The default branch (what Overleaf shows) is the only branch ever pushed; Overleaf's Git has one branch.
- `suggest` edits live on a local `agent/round-N` branch; the redline is the diff between the two.
- Files the tool commits itself (`review/`, `redline.tex`) are ignored when deciding whether the paper moved,
  otherwise every pull would rebase again.
- Comment-file conflicts (your reply and the agent's reply editing one JSON) are merged automatically; a conflict
  in the paper itself stops and rolls back.
- Local rollback tags `olmcp/pre-apply-<timestamp>` are never pushed (Overleaf's Git has no tags).

## Tests

119 tests, about 80 seconds, using real git and (where installed) real `latexdiff`/`latexmk`; nothing needs the
network or a real Overleaf.

| File | Covers |
|---|---|
| `test_basics.py` | Markers, anchors, config, sync lifecycle, text diff |
| `test_redline_flow.py` | Redline generation and annotation, accept/reject/pending, rollback, CI entry points |
| `test_local.py` | `pull`/`push` against a bare repo imitating Overleaf's remote |
| `test_overleaf.py` | Native comments against a fake `olcli` (`fake_olcli.py`), decisions in threads |
| `test_mcp.py` | The tools, path confinement, and a real stdio MCP session |
| `test_modes.py` | Tags, mixed rounds, the mode command |
| `test_build.py` | Rendering (needs `latexmk`) |

`conftest.py` provides `repo` (a git repo with a small paper), `world` (that repo plus a bare remote and a second
clone playing the researcher in Overleaf) and the `needs_latexdiff` / `needs_latexmk` skip markers. Tests that
need a missing tool are skipped, not failed.

**What no test can cover:** the real Overleaf and the real `olcli` output. Anything touching them needs the
manual checklist in [CONTRIBUTING.md](../CONTRIBUTING.md#testing-against-real-overleaf).

## Extending it

- **A new agent-facing operation:** add a method to `PaperTools` (raise `ToolError` for refusals), register it in
  `mcp_server.py` under `@expose`, mention it in `templates/AGENTS.md` and `docs/agents.md`, add tests.
- **A new CLI command:** a `cmd_*` function and an `add(...)` line in `cli.py`; keep stdout clean for `mcp`.
- **A new comment source:** produce comments through `Store.new(...)` with a distinct `origin.type`, as
  `sync.py` and `overleaf.py` do, and keep imports idempotent.
