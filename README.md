# agent-overleaf-connector (`olmcp`)

[![tests](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml)

**Let an AI agent (Claude Code, Codex, any MCP client) work on your Overleaf paper from your comments.**
Open source (Apache-2.0), nothing hosted: it runs on your machine against your own Overleaf project.

Overleaf has no connector for AI agents. This tool is that connector:

- **Comments in, with the exact text.** Select a passage in Overleaf's Review panel and comment; the agent
  gets your message, the selected text, and the thread. (Typing `%% @agent: ...` lines in the source works too.)
- **Edits out, as normal Overleaf edits.** The agent edits your files through Overleaf's Git integration and
  replies in the same comment thread, showing what it changed as a one-line diff.
- **You stay in control.** Per comment or by default, an edit is either applied at once (`direct`) or held
  for you to accept or reject (`suggest`). The agent never resolves or approves a thread; you do.
- **Agent-neutral.** One local MCP server and a CLI. The agent never touches git itself.

```
 Overleaf project ── Git + native comments ──  your clone  ──  AI agent
 (you comment here)        (olmcp-overleaf)      (olmcp)         (Claude Code / Codex / ...)
```

> Status: **0.9.x, early.** Tested with real git and TeX Live, a fake Overleaf comment API, and the MCP SDK's
> own client; used by the author with Claude Code and Codex on a real project. Not yet exercised by anyone else.
> See [what is verified and what is not](docs/status-and-roadmap.md).

## Quick start (new Overleaf project)

Needs Linux or macOS, Python 3.10+, git, and an Overleaf project with **Git integration** (a premium feature).
Full steps, with troubleshooting: **[docs/setup.md](docs/setup.md)**.

```bash
# 1. install (and, for native Overleaf comments, the Node client from this repository)
pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"
git clone https://github.com/nipdep/agent-overleaf-connector ~/agent-overleaf-connector
(cd ~/agent-overleaf-connector/node && npm install -g .)

# 2. log in with your Overleaf session cookie (never paste it into a chat)
olmcp-overleaf auth --cookie "<overleaf_session2 cookie value>"

# 3. clone your project (username: git, password: an Overleaf Git token) and set it up
git clone https://git@git.overleaf.com/<project-id> my-paper && cd my-paper
olmcp init --local --mode direct        # or --mode suggest
git add -A && git commit -m "Set up olmcp" && olmcp push
olmcp overleaf-check                    # should print: ok: project ...

# 4. connect your agent (from inside the clone)
claude mcp add olmcp -- "$(which olmcp)" mcp      # Claude Code
codex mcp add olmcp -- "$(which olmcp)" mcp       # Codex
```

Then comment in Overleaf and tell the agent: **"address the review comments"**.

## Everyday use

| You want to... | Do this |
|---|---|
| Ask for a change | Select text in Overleaf, add a Review comment (or type `%% @agent: ...` above a paragraph) |
| Choose how it is applied | Add `#suggest` or `#direct` to the comment; change the default with `olmcp mode suggest` |
| Focus or exclude the agent | Add `#agent` (work on these first) or `#no-agent` (hands off) to a comment; tags are optional |
| Accept a held change | Resolve the thread, or reply "accept", or set `accept` on its line in `redline.tex` |
| Reject or adjust it | Reply in the thread with what to change, or set `reject` in `redline.tex` |
| Undo an applied edit | Reply in the thread, `git revert` the commit, or use Overleaf's History |

Details: **[docs/usage.md](docs/usage.md)**.

## Documentation

| | |
|---|---|
| [docs/setup.md](docs/setup.md) | Setting up a new project, credentials, troubleshooting |
| [docs/usage.md](docs/usage.md) | Comments, modes, deciding, commands, configuration |
| [docs/agents.md](docs/agents.md) | Claude Code, Codex, other MCP clients, ChatGPT (status) |
| [docs/overleaf-client.md](docs/overleaf-client.md) | The own Node Overleaf client: comments, tracked-change edits, test checklist |
| [docs/ci-mode.md](docs/ci-mode.md) | The GitHub-sync alternative (no local machine) |
| [docs/architecture.md](docs/architecture.md) | How it works, for contributors |
| [docs/status-and-roadmap.md](docs/status-and-roadmap.md) | What is verified, what is open, what is planned |
| [docs/design.md](docs/design.md) | The full design record and the reasoning behind decisions |
| [CHANGELOG.md](CHANGELOG.md) | What changed in each version |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developing, testing, releasing |

## License

Apache-2.0. See [LICENSE](LICENSE).
