# Using it

## The loop

```
you comment in Overleaf  →  olmcp pull  →  agent addresses comments  →  olmcp push  →  you review
```

The agent runs `pull` first and `push` last (through MCP tools or the CLI), so normally you only comment,
say "address the review comments", and review. `pull` fetches what you did in Overleaf; `push` publishes the
agent's work. There is no daemon and no polling.

## Making a comment

**Native Overleaf comment** (needs `olmcp-overleaf`, see [setup](setup.md)): select text, add a Review comment. The agent
receives your message, the selected text (`selected_text`), and the thread. Later messages you write in the
thread are follow-ups the agent sees.

**Marker in the source** (no extra tools): on its own line directly above a paragraph, type
`@agent: your request` and press Ctrl+/ (Cmd+/ on Mac) to turn it into a comment. Continue a long request on
following lines starting `%% |`:

```latex
%% @agent: soften this claim and add a citation
%% | keep it to one sentence
Our method always outperforms the baselines on all benchmarks.
```

A marker covers the paragraph below it, up to the next blank line. For a figure or table put it above
`\begin{figure}`. Do not put it inside `tabular` or math. Editing a marker's text creates a new comment; the
agent removes the marker when it has handled it.

Only files the paper uses are scanned; keep comments out of `archive/` or `sample/` copies.

## Direct or suggest

- **`direct`** applies an edit to your files at once, as a normal Overleaf edit.
- **`suggest`** holds the edit for you to accept or reject in `redline.tex`.
- **`review`** writes the edit into Overleaf as a **tracked change** (Reviewing mode); you accept or reject it in
  Overleaf's Review panel. Needs a native comment and the Node client (see
  [overleaf-client.md](overleaf-client.md)); **not yet verified on real Overleaf**. Git is not touched: the accepted
  text arrives with your next `olmcp pull`.

Default: `olmcp mode` shows it, `olmcp mode suggest` (or `direct`) sets it (a committed one-line change; run
`olmcp push` to publish it), or tell the agent "switch to suggest mode".

Per comment: put `#suggest` or `#direct` anywhere in the comment (the older `[suggest]` / `direct:` at the start
still work). A tag is your choice and beats the default; the agent cannot override it and may choose only for untagged comments. A later tagged
message in a thread changes that comment's mode. Direct and suggest edits mix freely in one round.

## Comment tags (all optional)

Write hashtags anywhere in a comment, for example `we need to fix the wording here to shorten this #agent #suggest`.

| Tag | Effect |
|---|---|
| `#agent` | Focus: while any open comment has it, the agent is given only those comments this round |
| `#no-agent` | Hands off: the agent is not given the comment and its tools refuse to edit or reply to it |
| `#suggest` / `#review` / `#direct` | The comment's edit mode |

If tags conflict in one comment, the safe side wins: `#no-agent` beats `#agent`, `#suggest` beats `#review` beats `#direct`. A
later message in a thread that carries a tag changes the comment's tag. Focus is advisory (you can tell the agent
"do all comments"); `#no-agent` is enforced. Tags are removed from the request the agent reads. Without any tag
everything works as before; set `comment_tags: false` to ignore tags entirely.

## What the agent's reply shows

For a native comment the agent posts into the thread, prefixed `[agent]`:

```
[agent] Softened the claim.

Proposed edit in sections/results.tex:
Our method [-always-] outperforms [-the-]{+most+} baselines on the benchmarks
(Proposed change, not applied yet: resolve this thread to accept it, or reply here to reject or adjust it.)
```

"Proposed edit" (with the decide footer) for `suggest`, "Edit applied" for `direct`. `[-removed-]{+added+}`
is an inline word diff. The agent never resolves a thread: **a handled comment stays open until you resolve it**
(there is no setting that changes this).

## Deciding on a held change (suggest)

| How | Accept | Reject or adjust |
|---|---|---|
| In the Overleaf thread | Resolve it (the check mark), or reply "accept", "ok", "lgtm" or a thumbs-up | Reply with what to change, or `reject: reason` |
| In `redline.tex` | Set `decision[C-0003]: accept` | Set `reject`, optionally fill `reason[C-0003]:` |
| Everything at once | `%% decision[*]: accept-all` | `%% decision[*]: reject-all` |

A decision on one comment beats the `*` line, and a decision typed in `redline.tex` beats the thread. Nothing
counts until the agent has answered in the thread. Decisions take effect on the next `olmcp pull`; the accepted
text reaches your Overleaf project after `olmcp push`, so run `olmcp pull && olmcp push` or ask the agent to.

A rejected change is dropped and its comment reopens; your reply or reason is the instruction for the next
attempt. Decisions cover a whole comment, not single hunks.

### Reading `redline.tex`

Set `redline.tex` as the main document in Overleaf to see the typeset redline (struck-through red, underlined
blue). It sits beside your main file. Above every change a note says where it is:

```
%% >> C-0005, change 1 of 2, sections/01_introduction.tex:14
%%    asked: drop the single-block qualifier
%%    edit:  ...policy-compliant [-single-block-] queries without trusting...
%% decision[C-0005]: pending   <- accept | reject (decides all 2 changes of C-0005)
%% reason[C-0005]:
```

Edit only the `decision[...]` and `reason[...]` lines; valid values are `accept`, `reject`, `pending`. If a
change has no visible effect on the paper, its decision lines are at the top under a `WARNING`.

## Undoing

- Direct edit: reply in the thread, `git revert` the commit (it carries `Resolves: C-xxxx`), or Overleaf's History.
- An accepted change: the same. A local rollback tag `olmcp/pre-apply-...` marks the state before each accept.

## Commands

All commands accept `--root <dir>`; most listing commands accept `--json`. Run `olmcp <command> --help`.

| Command | What it does |
|---|---|
| `init [--local] [--mode M] [--force]` | Add config, agent instructions and Claude Code files to a repo (`--local`: Overleaf Git, no CI) |
| `pull` | Fetch your edits, import comments (markers and native), apply decisions, report what happened |
| `push` | Refresh the redline and change log, post agent replies to threads, publish to Overleaf |
| `mode [direct\|suggest]` | Show or set the default mode |
| `list [--status ...]`, `show ID` | Comments and their conversation |
| `address ID [file.json]` | Address one comment: edits + reply + commit, atomically (for agents with only a shell) |
| `reply ID TEXT`, `resolve ID` | Reply without editing; mark a comment addressed |
| `overleaf-check [--raw]` | Verify access to Overleaf's comments through `olmcp-overleaf` |
| `mcp` | Run the MCP server (stdio) for Claude Code, Codex and others |
| `doctor` | Check git, TeX, latexdiff, main file, Overleaf comments |
| `build` | Render the paper (PDF, page images); needs TeX |
| `redline BRANCH`, `apply`, `sync`, `changelog`, `round`, `ci` | Lower-level steps used by the above and by CI mode |

## Settings (`.olmcp.yml`)

All optional. The old name `.paper-review.yml` is still read, and `olmcp init` renames it.

| Key | Default | Meaning |
|---|---|---|
| `mode` | `direct` | Default edit mode (`direct` or `suggest`) |
| `main` | detected | Main `.tex` file, if detection picks the wrong one |
| `engine` | detected | `pdflatex`, `xelatex` or `lualatex`; only matters for local builds |
| `comment_tags` | `true` | Set `false` to ignore `#agent`, `#no-agent`, `#suggest`, `#direct` |
| `overleaf_comments` | `true` | Set `false` to turn native Overleaf comments off |
| `overleaf_project` | from the remote URL | Override the project id |
| `overleaf_client` | `olmcp-overleaf` | Command used to reach Overleaf (the old key `olcli` still works) |
| `remote`, `remote_branch` | `origin`, the default branch | Git remote and branch to sync with |
| `default_branch` | detected | The branch Overleaf shows (`master` or `main`) |
| `marker` | `agent` | The word in `%% @agent:` markers |
| `review_dir`, `build_dir` | `review`, `build` | Where generated files go |
| `page_dpi` | `110` | Resolution of rendered pages |

## Files the tool creates

| Path | What |
|---|---|
| `review/comments/C-NNNN.json` | One file per comment: request, anchor, the whole conversation, status |
| `redline.tex` (beside the main file), `review/redline.json` | The current redline and its machine file |
| `review/CHANGELOG.md` | What changed and why, from `Resolves: C-NNNN` commit trailers |
| `build/` | Local renders (git-ignored) |

Comment statuses: `open` (needs the agent), `addressed` (the agent handled it; you decide), `resolved` (you
closed it or accepted its change), `wontfix` (deleted in Overleaf).
