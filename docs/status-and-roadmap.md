# Status and roadmap

Version 0.10.x. Early: used by the author on a real project; not yet by anyone else. This page is the honest
list of what is proven, what is not, and what is open. Update it with every change that moves something between
columns.

## What is verified

| Area | How | State |
|---|---|---|
| Comment lifecycle, markers, modes, decisions, redline, `pull`/`push`, MCP tools | 148 automated tests with real git; CI runs them on every push | Verified |
| Redline compiles (31-page journal paper, figures and bibliography) | Run locally with TeX Live | Verified |
| MCP server | The MCP SDK's own client over stdio | Verified |
| CI mode on GitHub Actions (full round, accept/reject, bot commits, tags) | Real runs on a demo paper and a real paper | Verified |
| Local mode against Overleaf's Git (push appears, pull sees comments) | The author, on a real project | Verified by the author |
| Native comments: import with selected text, agent replies in the thread | The author, with the real `olcli` | Verified by the author |
| Use from Claude Code and Codex | The author | Verified by the author |
| Redline opened as main document in Overleaf | The author | Verified by the author |

## Not verified

| Area | Why it matters |
|---|---|
| Deciding in the thread (resolve = accept, reply = reject) against real Overleaf | Tested against a fake `olcli` only |
| The 0.8 behaviour change (agent no longer resolves threads) 0.9 mode tags and 0.10 hashtags (`#agent`, `#no-agent`, `#suggest`, `#direct`) on a real project | New |
| The exact `olcli comments list --json` output across versions | Undocumented upstream; the parser accepts the documented fields and aliases |
| `olmcp-overleaf` (Node client: comments, replies, tracked-change edits) against real Overleaf | Tested against a fake server only; checklist in overleaf-client.md |
| `review` mode (edits as Overleaf tracked changes) | Not tried on real Overleaf; fake only |
| Large projects (many documents) | `olcli` fetches every document; each call re-lists |
| macOS, Windows | Linux only |
| Other MCP clients, other agents following `AGENTS.md` | Only Claude Code and Codex used |
| Private repositories and protected branches in CI mode | |
| Whether Overleaf's Git exposes `master` or `main` for every project | One project showed `main`; the tool detects the name |

## Known limits

- Decisions cover a whole comment, not single hunks.
- `#suggest` / `#direct` apply per comment, not per edit; `#agent` focus is advisory, `#no-agent` is enforced.
- The word diff and the file/line locations are best effort; a change with no visible effect on the paper is
  flagged with a warning, not silently dropped.
- Native comments rely on an unofficial API and a browser session cookie that expires after a few days.
- No ChatGPT chat (web or desktop) support; use Codex.
- Overleaf's own warning applies: pushing from Git can displace tracked changes and comments in a file; this tool
  neither creates tracked changes nor protects existing ones.

## Open decisions

| Question | Where it stands |
|---|---|
| Keep the review machinery (suggest mode, redline, decisions) as built, or make it optional and default to a thin connector with neutral `checkpoint` / `diff` / `revert` tools and instruction recipes | Proposed, not decided |
| The agent's edits as Overleaf tracked changes (Reviewing mode) | Investigated, not built: `olcli` cannot write them, Git cannot create them, and Overleaf warns against mixing them with Git. An experiment is written up in design.md section 21 |
| ChatGPT chat support | Needs an HTTP mode, a user-run tunnel and real authentication (design.md section 19) |
| Final name and distribution | Command `olmcp`, package and repository `agent-overleaf-connector`, not on PyPI; no release tags yet |
| Per-hunk decisions | Designed (design.md section 7), not built |

## Planned, roughly in order

1. Release tags (`vX.Y.Z`) and GitHub releases, so installs can be pinned.
2. Optional rendering made first-class: `olmcp setup` that explains each dependency, a paper-aware `doctor`.
3. `--main` and a dependency tree (only files the paper uses are scanned and diffed).
4. Diff-based review: hunk ids, patches saved per comment, a generated review file.
5. A render mirror in CI so agents without local TeX can still see pages.
6. macOS and Windows checks; PyPI.

The reasoning, alternatives and status tags for each item are in [design.md](design.md).
