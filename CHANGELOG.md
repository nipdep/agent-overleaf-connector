# Changelog (the tool, not your paper's change log)

Bump `version` in `pyproject.toml` for every change that users can notice, and add a line here.

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
