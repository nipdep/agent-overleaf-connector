# Changelog (the tool, not your paper's change log)

Bump `version` in `package.json` for every change that users can notice, and add a line here.


## 0.6.1
- In `review` mode the thread reply is only the agent's words: Overleaf already shows the tracked change, so the
  Before/After block and the footer are gone. `direct` edits keep Before/After, because they leave no visible trace.

## 0.6.0
- **Clearer agent replies.** The thread reply is the agent's one-to-three plain sentences, then **Before / After** of the
  changed passage (cropped to the changed words plus context) and one line on what to do next. The `[-old-]{+new+}`
  diff markup and the long footer are gone. The tool description and `AGENTS.md` tell the agent to write short, plain
  replies and not to paste diffs.

## 0.5.0
- **No clone or per-folder setup.** Every tool takes an optional `project` argument (an id, a project URL or a git
  URL), so the server can be registered once for all folders and the agent told which project to work on; the
  server's own instructions carry the rules. `olmcp init` is now optional. `olmcp mcp` starts without a project.

## 0.4.0
- **The command is now `olmcp`** (package `olmcp`). `olmcp-overleaf` stays as an alias so existing registrations keep
  working. The project file is `.olmcp.json` and the cookie file `~/.config/olmcp/config.json`; the old names
  (`.olmcp-overleaf.json`, `~/.config/olmcp-overleaf/config.json`) are still read. If the Python tool is still
  installed, uninstall it: `pipx uninstall agent-overleaf-connector`.

## 0.3.0 (Node-only)
- **The tool is now only the Node program `olmcp-overleaf`.** Install with `npm install -g github:nipdep/agent-overleaf-connector`.
  It works on the live Overleaf project: comments (selected text, threads), edits as **tracked changes** (`review`,
  default) or plain edits (`direct`), replies with a word diff, PDF from Overleaf's compiler, tags (`#agent`,
  `#no-agent`, `#review`/`#suggest`, `#direct`), an MCP server and a CLI, `init` and `doctor`. No Git integration or
  paid Overleaf plan is needed; no local state (a comment's status comes from its thread).
- **Removed** (still on the `python-legacy` branch): the Python tool, Git sync, `%% @agent:` markers, `redline.tex`,
  the branch-based suggest mode, GitHub CI mode.
- Earlier entries below describe the Python version (0.1.0 to 0.12.0) and the `olmcp-overleaf` client builds.

## 0.10.0
- **Optional hashtags in comments.** `#agent` (focus), `#no-agent` (hands off, enforced by the tools),
  `#suggest` / `#direct` (mode), anywhere in a comment or a later thread message. Conflicts resolve to the safe
  side. `pull`, `list` and `list_comments` show focus and skipped comments (`include_skipped` to see all).
  `comment_tags: false` disables them. The 0.9 start-of-comment forms still work.

## 0.11.0
- **`review` mode: the agent's edits as Overleaf tracked changes.** `mode: review`, `#review` in a comment, or
  `address_comment(mode="review")` writes the edit through `olmcp-overleaf edit` (Reviewing mode) and records only the
  conversation in git; you accept or reject in Overleaf. Native comments only. Not yet verified on real Overleaf.

## 0.12.0
- **`olcli` is gone.** The Overleaf client is `olmcp-overleaf` (`node/`) and the default; the config key is now
  `overleaf_client` (the old `olcli` key is still read). Install with `npm install -g .` in `node/`.
- **`auto_resolve_threads` is removed**: the tool never resolves, reopens or deletes a thread (the client has no such
  command). The key is ignored and `doctor` says so.
- `olmcp guard` now denies `olmcp-overleaf` and the legacy `olcli` for agents.

## Node client history (before 0.3.0)
- **`olmcp-overleaf` 0.2.0 is a Node-only tool of its own**: an MCP server (`olmcp-overleaf mcp`) and CLI with
  `list_comments`, `show_comment`, `read_file`, `list_files`, `address_comment` (tracked changes or plain edits plus the
  thread reply), `reply_to_comment`, `list_tracked_changes`, `render_pdf`; `#agent` / `#no-agent` / `#review` /
  `#suggest` / `#direct` tags; `init`. Overleaf is the store (no local state, no git). Tested against a fake
  Overleaf and the official Python MCP client; not yet run by an agent on a real project.
- `olmcp-overleaf pdf <project> [-o file]` compiles with Overleaf's own compiler and saves the PDF (a failed compile
  prints the TeX error lines). Tested against a fake Overleaf only.
- **`olmcp-overleaf`** (`node/`): our own Overleaf client in plain Node (credit to olcli, MIT): comments, replies,
  tracked changes, and edits written as tracked changes (Reviewing mode). No resolve/reopen/delete commands by
  design. Drop-in for `olcli` (`olcli: olmcp-overleaf`). Tested against a fake Overleaf only; see
  docs/overleaf-client.md for the scratch-project checklist. A Node job runs its tests in CI.
- `olmcp guard [--codex]` and `olmcp init` deny agents the `olcli` command (Claude Code `.claude/settings.json`, merged not
  overwritten; Codex rule file in `~/.codex/rules/olmcp.rules`), so an agent cannot resolve threads behind the tool's
  back. `doctor` checks it.
- `pull` re-reads the tags of every message in an already imported thread, so comments imported by an older
  version pick up their `#suggest` / `#direct` / `#agent` / `#no-agent` tags. `pull` and `doctor` print the version.
- Documentation set: a short README front page and `docs/` (setup, usage, agents, CI mode, architecture, status and
  roadmap), `CONTRIBUTING.md` (development, a manual checklist for real Overleaf, releasing), a test workflow that
  runs the suite on Python 3.10, 3.12 and 3.13, and issue and pull request templates.

## 0.9.0
- **Switch direct/suggest easily, and per comment.** `olmcp mode [direct|suggest]` shows or sets the default (a
  committed one-line change; the `set_mode` tool does the same). A comment, follow-up message or `%% @agent:`
  marker that starts with `[suggest]`, `[direct]`, `suggest:` or `direct:` chooses its own mode; the researcher's
  tag beats the default and the agent's `mode` argument (agents may choose only for untagged comments).
  `list_comments` / `show_comment` / `pull` show each comment's mode. Direct and suggest edits mix in one round
  (the round branch is rebased onto direct edits before a suggest edit). Thread replies say "Proposed edit" or
  "Edit applied" by each comment's own mode. `address_comment` and `olmcp address` accept `mode`.

## 0.8.0
- **The agent no longer approves or closes comments.** Handling a comment (direct or suggest mode) sets its
  status to `addressed` instead of `resolved`, and `push` no longer resolves the Overleaf thread, so the comment
  stays visible in the Review panel until the researcher resolves it (which `pull` mirrors as `resolved`). A
  follow-up reply reopens it. `olmcp resolve` now also only marks a comment `addressed`. `AGENTS.md` and the
  tool descriptions tell agents never to resolve, close, approve or dismiss a thread.
- `auto_resolve_threads: true` in `.olmcp.yml` restores the old behaviour (default: off).

## 0.7.1
- **Every change in `redline.tex` is annotated where it happens.** Above each change a `>>` note gives the
  comment id, "change 2 of 3", the real file and line (`sections/01_introduction.tex:14`), what you asked
  (`asked:`) and the edit in words (`edit:  ...compliant [-single-block-] queries...`). Later changes of the same
  comment say which decision lines cover them, and the decision line states how many changes it decides. The
  header now points to `olmcp pull` (it still said "push to GitHub").

## 0.7.0
- **The change appears in the comment thread.** The agent's reply in the Overleaf thread now includes the edit
  itself as an inline word diff (`kept [-removed-]{+added+} kept`), labelled "Proposed edit" (suggest mode) or
  "Edit applied" (direct mode), so the comment, the change and the accept/reject controls are in one place in
  the Review panel instead of the change living only in `redline.tex`. The edits are stored with the reply in
  the comment file.

## 0.6.0
- **Renamed.** The command is now **`olmcp`** (Overleaf + MCP: short to type); the installable package and
  repository are **`agent-overleaf-connector`**; the Python module is `olmcp`. `paper-review` still works as a
  deprecated alias (it prints a note on stderr). Install:
  `pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"`.
- Config file is now `.olmcp.yml`; `.paper-review.yml` is still read, and `olmcp init` renames it (keeping its
  settings). Generated redlines from before the rename are still recognised. The MCP server is named `olmcp`;
  bot commits and rollback tags read `olmcp: ...` / `olmcp/pre-apply-...` (older ones keep the old prefix).
- Uninstall the old package first: `pipx uninstall paper-review` (both would provide a `paper-review` command).

## 0.5.0
- **Decide in the Overleaf thread.** When the agent has proposed a change (`suggest` mode) its reply in the
  thread says so; **resolving the thread accepts the change** and **replying rejects or adjusts it** (a reply
  that says "accept", "ok", "lgtm" or a thumbs-up accepts; "reject: reason" rejects with that reason; any other
  reply rejects and is the instruction for the next attempt). It feeds the same `apply` step as the
  `decision[...]` lines in `redline.tex`; a decision typed in the file wins. Nothing counts until the agent has
  answered in the thread.
- **The project id is automatic**: read from the clone's Overleaf remote URL (`git.overleaf.com/<id>`, or a
  self-hosted `.../git/<id>`); `overleaf_project` is only an override and `overleaf_comments: false` turns the
  feature off. Detection looks at the host, so a GitHub URL is never mistaken for Overleaf. If `olcli` is not
  installed, `pull` says so in one line instead of warning.
- Fix: comment-file conflicts (a researcher's reply and the agent's reply both editing one comment's JSON)
  are merged automatically when accepting or rebasing, keeping both conversations; conflicts in the paper
  itself still stop and report.

## 0.4.1
- `pull` now always says whether Overleaf comments are on ("N thread(s) checked, ...") or off (with the setting
  to add); before, "off" and "on but nothing found" both printed nothing.
- The marker count is labelled `markers removed` (the agent removes markers too, not only the researcher).

## 0.4.0
- **Native Overleaf comments** (optional, needs the community CLI `olcli`, MIT): select text in Overleaf's
  Review panel and comment; `pull` imports each thread with its selected text as the comment's anchor
  (`selected_text` in the tools); `push` posts the agent's reply into the same thread prefixed `[agent] `, and
  the thread is resolved when the change is accepted (`direct` mode: on push). Follow-ups you write there reopen
  the comment; resolving or deleting a thread there is mirrored. Enable with `overleaf_project: <id>`;
  `paper-review overleaf-check` verifies access. Unofficial API and session cookie (kept by olcli, never seen by
  this tool); every olcli failure is a warning, never fatal.
- `init` adds `.olauth` to `.gitignore` (olcli's plaintext credentials).

## 0.3.0
- **MCP server** (`paper-review mcp`, optional extra `paper-review[mcp]`): tools `pull`, `list_comments`,
  `show_comment`, `read_file`, `list_paper_files`, `address_comment`, `reply_to_comment`, `push`, `build`,
  `view_page` for Claude Code, Codex and other MCP clients that start a local (stdio) server. The protocol is
  enforced in code: `address_comment` applies the edits (each `old` must match exactly once), removes the
  marker, records the reply, resolves the comment and commits with the `Resolves:` trailer, all or nothing;
  branches, pushes and ids are never the agent's job; paths are confined to the repository.
- `paper-review address C-0001 edit.json`: the same atomic operation for agents that only have a shell.
- `init` writes `.mcp.json` and `.claude/commands/address-comments.md`; `CLAUDE.md` imports `AGENTS.md`;
  `AGENTS.md` rewritten around "address the comments": pull, one call per comment, push; never push a branch to
  Overleaf.
- Tool errors reach the agent with their message (the SDK hides all other exceptions).

## 0.2.2
- `init --local` no longer writes `remote_branch: master`. A real Overleaf project exposed `main`, so the
  hard-coded name made `push` target the wrong branch. The branch is detected from the clone.

## 0.2.1
- A commit whose change cannot appear in the redline (it touches files `main.tex` does not input, or only
  comments/whitespace) is now flagged with a warning in `redline.tex`, in `redline.json`, and in the
  output of `redline` / `pull` / `push`. It used to produce a redline with no visible change and no message.

## 0.2.0
- Local mode: `paper-review pull` / `push` around an agent task (Overleaf Git remote, no CI, no polling).
- `init --local`; `remote` / `remote_branch` config.
- **The redline moved:** `redline.tex` now sits beside the main file instead of `review/redline.tex`
  (so Overleaf resolves its paths like the paper's). A leftover `review/redline.tex` is removed on
  the next `push`, with typed decisions carried over.
- The generated redline is never chosen as the main file nor scanned for markers.
- Pushes the pre-apply rollback tag in CI mode; real unresolved-reference count in `build.json`.
- Design v2 document (diff-based review, replies, dependency tree; mostly planned).

## 0.1.0
- First version: build, marker comments, `direct` / `suggest` modes, flattened latexdiff redline,
  accept/reject via `apply`, change log, reusable GitHub workflow.
