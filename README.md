# Agent–Overleaf Connector (`olmcp`)

[![tests](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml)

`olmcp` lets an AI coding agent work on your Overleaf paper without taking you out of the review loop.

You leave a comment in Overleaf. The agent reads the comment and its selected text, edits the paper, and replies in the same thread with a short summary and a word-level diff. You decide whether changes should be applied immediately or held for review.

The project is open source under Apache 2.0. Nothing is hosted for you: it runs on your computer and connects to your own Overleaf project.

## What it gives you

- **A familiar way to ask for changes.** Select text and leave a normal Overleaf Review comment. You can also add `%% @agent:` comments directly to the LaTeX source.
- **Edits that return to Overleaf.** The connector uses Overleaf's Git integration to publish the agent's work.
- **Control over every change.** Use `direct` mode to apply edits immediately or `suggest` mode to review them first. A comment can also choose its own mode.
- **Replies that stay with the discussion.** The agent responds in the original thread and shows what changed.
- **Support for different agents.** The same local MCP server works with Claude Code, Codex, and other clients that can start a local MCP server.

```text
You comment in Overleaf
        ↓
olmcp brings the comment to your local clone
        ↓
Your AI agent edits the paper
        ↓
olmcp publishes the edit and reply to Overleaf
```

> **Project status:** version 0.12.x, still early. The author uses it with Claude Code and Codex on a real project, and the core workflow has automated test coverage. Some Overleaf behavior relies on an unofficial API and still needs broader real-world testing. See [Status and roadmap](docs/status-and-roadmap.md) for details.

## Before you start

You need Linux or macOS, Python 3.10 or newer, Git, and an Overleaf project with **Git integration**. Overleaf Git integration is a premium feature, although a free account can use it in a project owned by a premium user.

Node.js 20 or newer is also needed if you want native Overleaf comments and tracked changes.

## Quick start

For explanations and troubleshooting, follow the [full setup guide](docs/setup.md). The short version is:

### 1. Install the connector

```bash
pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"

# Optional: install the client for native Overleaf comments
git clone https://github.com/nipdep/agent-overleaf-connector ~/agent-overleaf-connector
(cd ~/agent-overleaf-connector/node && npm install -g .)
```

### 2. Sign in to Overleaf comments

```bash
olmcp-overleaf auth --cookie "<overleaf_session2 cookie value>"
```

Never paste this cookie into a chat, issue, or commit. It gives access to your Overleaf account. The [setup guide](docs/setup.md#2-add-your-overleaf-credentials) explains where to find it and how it is stored.

### 3. Clone and prepare your paper

Use `git` as the username and an Overleaf Git token as the password:

```bash
git clone https://git@git.overleaf.com/<project-id> my-paper
cd my-paper

olmcp init --local --mode direct   # use --mode suggest to review edits first
git add -A
git commit -m "Set up olmcp"
olmcp push
olmcp overleaf-check
```

The last command should print `ok: project ...`.

### 4. Connect your agent

Run one of these commands from inside the cloned project, then restart the agent:

```bash
claude mcp add olmcp -- "$(which olmcp)" mcp
codex mcp add olmcp -- "$(which olmcp)" mcp
```

Now select a sentence in Overleaf, leave a comment such as “make this clearer,” and tell the agent:

> Address the review comments.

## Common tasks

| When you want to… | Do this |
|---|---|
| Request a change | Select text and leave an Overleaf Review comment, or add `%% @agent: your request` above a paragraph |
| Review an edit before it is applied | Add `#suggest` to the comment |
| Apply an edit immediately | Add `#direct` to the comment |
| Ask the agent to focus on selected threads | Add `#agent` to those comments |
| Keep the agent away from a thread | Add `#no-agent` |
| Accept a suggested edit | Resolve the thread, reply `accept`, or mark it `accept` in `redline.tex` |
| Reject or revise a suggestion | Reply with what should change, or mark it `reject` in `redline.tex` |
| Undo an applied edit | Reply in the thread, revert the Git commit, or use Overleaf History |

See [Using `olmcp`](docs/usage.md) for modes, comment tags, decisions, commands, and configuration.

## Documentation

- [Set up a project](docs/setup.md)
- [Use comments, modes, and decisions](docs/usage.md)
- [Connect Claude Code, Codex, or another agent](docs/agents.md)
- [Understand the Overleaf comment client](docs/overleaf-client.md)
- [Run through GitHub Actions instead of locally](docs/ci-mode.md)
- [Understand the architecture](docs/architecture.md)
- [Check current limitations and planned work](docs/status-and-roadmap.md)
- [Read the detailed design record](docs/design.md)
- [Contribute to the project](CONTRIBUTING.md)

Release-by-release changes are listed in the [changelog](CHANGELOG.md).

## License

Apache 2.0. See [LICENSE](LICENSE).
