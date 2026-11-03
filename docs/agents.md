# Connecting an AI agent

The agent talks to your Overleaf project only through this tool. The tool does the git work, the comment
handling and the bookkeeping; the agent supplies the edits and the wording.

## How the pieces fit

| Piece | What it is |
|---|---|
| `olmcp mcp` | A local MCP server (stdio) exposing the tools below. The agent client starts it |
| `AGENTS.md` | The protocol, in plain text. Codex reads it; `CLAUDE.md` imports it for Claude Code |
| `.mcp.json` | Claude Code's project entry for the server (it asks you to approve it) |
| `.claude/commands/address-comments.md` | The `/address-comments` command |

All four are written into your clone by `olmcp init`. Run the agent from inside the clone.

## Claude Code

```bash
claude mcp add olmcp -- "$(which olmcp)" mcp
claude mcp list                  # olmcp should show as connected
```

Restart Claude Code afterwards. Then say "address the review comments", or type `/address-comments`.
Using the full path from `which olmcp` avoids problems when the agent's shell has a different `PATH`.

## Codex (CLI, IDE extension, app)

```bash
codex mcp add olmcp -- "$(which olmcp)" mcp
codex mcp list
```

Or in `~/.codex/config.toml` (a project-level `.codex/config.toml` also works for trusted projects):

```toml
[mcp_servers.olmcp]
command = "olmcp"
args = ["mcp"]
```

Codex reads `AGENTS.md` automatically. These are the author's tested setups (Codex "works well"); the details
come from Codex's documentation, which the maintainer could not fetch while writing this page, so correct
this page if the commands differ in your version.

## Other MCP clients that start local servers

Claude Desktop, Cursor and similar: command `olmcp`, arguments `["mcp"]`, working directory the clone (or add
`--root <clone>` before `mcp`). Untested.

## ChatGPT (chat in the browser or desktop app): not supported yet

ChatGPT's custom connectors need a **remote** MCP server over HTTPS (Developer Mode, plan dependent; OAuth or no
authentication) and cannot start a local program. This server speaks over a local pipe only. Supporting it
would need an HTTP mode, a tunnel you run yourself, and real authentication, because the server can edit your
paper and push to Overleaf; an open URL would hand that to anyone who finds it. That authentication is the
unbuilt, hard part. See `design.md` section 19. Until then the OpenAI route is **Codex**.

## The tools

| Tool | Does |
|---|---|
| `pull` | Fetch your edits from Overleaf, import comments, apply your decisions, report what happened. Always first |
| `list_comments`, `show_comment` | Open comments with their request, selected text, mode and thread |
| `read_file`, `list_paper_files` | Read parts of the paper's text files |
| `address_comment` | Address one comment: apply edits, remove its marker, record the reply, mark it addressed, commit. All or nothing |
| `reply_to_comment` | Reply (a question or explanation) without changing the paper; the comment stays open |
| `set_mode` | Change the default mode; only when you ask |
| `push` | Refresh the redline and change log, post replies into Overleaf threads, publish. Last |
| `build`, `view_page` | Optional: render the paper and look at a page (needs TeX) |

## What the tools enforce (so the agent cannot get it wrong)

- `address_comment` is atomic: every edit's `old` text must match exactly once, or nothing changes and the
  error says how to retry.
- One comment per commit, with the `Resolves: C-NNNN` trailer; the reply is recorded with the edit.
- Your `#suggest` / `#direct` tag beats the agent's `mode` argument.
- A `#no-agent` comment cannot be edited or replied to; with any open `#agent` comment, `list_comments` returns
  only those unless the agent passes `include_skipped`.
- Paths stay inside the repository; only `.tex`, `.bib` and `.sty` can be edited; `.git`, `build/` and `review/`
  cannot; symlinks out of the repository are refused. There is no tool that runs arbitrary commands.
- The agent never creates branches, pushes by itself, or resolves a thread.
- Errors from the tools reach the agent with their message.

What is only *instruction* (in `AGENTS.md`, which you can edit): how to word replies, when to ask instead of
guess, which mode to choose for untagged comments, "never push a branch to Overleaf".

## No MCP? Use the CLI

An agent with only a shell can follow the same loop:

```bash
olmcp pull
olmcp list
olmcp show C-0001
olmcp address C-0001 edit.json     # JSON: {"edits": [{"file", "old", "new"}], "reply": "...", "mode": "..."}
olmcp push
```

## Changing how the agent behaves

Edit `AGENTS.md` in your clone. Examples: "for any change that deletes text, use `mode: suggest`", "ask me
before touching the abstract", "always explain in one sentence". The tool does not prescribe a review policy;
your instructions and your comment tags do.

## What has been verified

The real server driven over stdio by the MCP SDK's own client (tool list, a full address-and-push round, error
messages reaching the agent), and use with Claude Code and Codex on a real project by the author. Other
clients and other agents' adherence to `AGENTS.md` are untested.
