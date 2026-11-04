# Status and roadmap

The project is at version 0.12.x and is still early. The author uses it on a real project, but it has not yet been tested by a wider group of users.

This page separates what has been verified from what still needs real-world testing. It also records current limitations and the next planned work.

## What is verified

| Area | How | State |
|---|---|---|
| Comment lifecycle, markers, modes, decisions, redline, `pull`/`push`, MCP tools | 148 automated tests with real git; CI runs them on every push | Verified |
| Redline compiles (31-page journal paper, figures and bibliography) | Run locally with TeX Live | Verified |
| MCP server | The MCP SDK's own client over stdio | Verified |
| CI mode on GitHub Actions (full round, accept/reject, bot commits, tags) | Real runs on a demo paper and a real paper | Verified |
| Local mode against Overleaf's Git (push appears, pull sees comments) | The author, on a real project | Verified by the author |
| Native comments: import with selected text, agent replies in the thread | The author, first with `olcli`, then `olmcp-overleaf check` read all 15 threads of a real project | Reading verified by the author; replies and import through the new client not yet re-run |
| Use from Claude Code and Codex | The author | Verified by the author |
| `review` mode: the agent's edit appears as a tracked deletion and insertion with a thread reply | The author, on a real project (Overleaf Review panel) | Verified by the author |
| Redline opened as main document in Overleaf | The author | Verified by the author |

## Not verified

| Area | Why it matters |
|---|---|
| Deciding in the thread (resolve = accept, reply = reject) against real Overleaf | Tested against a fake client only |
| The 0.8 behaviour change (agent no longer resolves threads) 0.9 mode tags and 0.10 hashtags (`#agent`, `#no-agent`, `#suggest`, `#direct`) on a real project | New |
| What Overleaf's comment endpoints return across versions | Undocumented; the parser accepts the known fields and aliases |
| `olmcp-overleaf` (Node client: comments, replies, tracked-change edits) against real Overleaf | Tested against a fake server only; checklist in overleaf-client.md |
| Node-only `olmcp-overleaf mcp` driven by Claude Code or Codex on a real project | Only the fake Overleaf and a Python MCP client so far |
| Large projects (many documents) | the client joins every document; each call re-lists |
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
| The agent's edits as Overleaf tracked changes (Reviewing mode) | Built as `review` mode (design.md section 26) through `olmcp-overleaf`; not yet tried on real Overleaf. Overleaf warns against mixing them with Git pushes |
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
