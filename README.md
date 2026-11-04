# Agent–Overleaf Connector (`olmcp`)

[![tests](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml)

`olmcp` lets an AI coding agent work on your Overleaf paper without taking you out of the review loop.

You leave a comment in Overleaf. The agent reads the comment and its selected text, edits the paper as **tracked changes** you can accept or reject, and replies in the same thread. You stay in charge of every change.

The project is open source under Apache 2.0. Nothing is hosted for you: it runs on your computer and connects to your own Overleaf project.

## What it gives you

- **A familiar way to ask for changes.** Select text and leave a normal Overleaf Review comment.
- **Edits that appear where you already review.** In the default `review` mode the agent's change shows up in the editor as a tracked deletion and insertion, with Accept and Reject buttons. Reject restores your text.
- **Control over every comment.** Add `#direct` to apply an edit immediately, `#no-agent` to keep the agent away from a thread, or `#agent` to focus it on selected threads. Tags are always optional.
- **Replies that stay with the discussion.** The agent answers in the original thread in plain words. It never resolves, closes, or approves a thread; the tool has no such command.
- **A look at the result.** The agent can compile the project with Overleaf's own compiler and read the PDF.
- **Support for different agents.** The same local MCP server works with Claude Code, Codex, and other clients that can start a local MCP server.

```text
You comment in Overleaf
        ↓
Your AI agent reads the comment through olmcp
        ↓
olmcp writes the edit into Overleaf as a tracked change
        ↓
You accept, reject, or reply in the thread
```

> **Project status:** version 1.0.0-alpha.1. The author uses it with Claude Code and Codex on a real project, and the core workflow has automated test coverage. The tool relies on Overleaf's unofficial web interface, so it needs broader real-world testing. Want to help? Follow the [alpha test plan](docs/alpha-test-plan.md). See [Status and roadmap](docs/status-and-roadmap.md) for details.

## Before you start

You need **Node.js 20 or newer** and an Overleaf account. That is all: there is no Python, no Git, no TeX to install, and no paid Overleaf plan or Git integration is required. Nothing needs to be cloned or set up per project.

Everything heavy (reading the document, tracking changes, compiling, rendering) happens on Overleaf's servers. The program only talks to Overleaf over HTTPS and to your agent over a local pipe, so it is not tied to an operating system. The tests run on Linux and macOS; Windows has not been tested yet.

## Quick start

For explanations and troubleshooting, follow the [full setup guide](docs/setup.md). The short version is:

### 1. Install `olmcp`

```bash
npm install -g github:nipdep/agent-overleaf-connector
olmcp --version
```

If you used the earlier Python version of `olmcp`, uninstall it first with `pipx uninstall agent-overleaf-connector`.

### 2. Sign in to Overleaf

```bash
olmcp auth --cookie "<overleaf_session2 cookie value>"
```

Never paste this cookie into a chat, issue, or commit. It gives access to your Overleaf account. The [setup guide](docs/setup.md#2-sign-in-with-your-session-cookie) explains where to find it and how it is stored.

### 3. Connect your agent

Run one of these commands once, then restart the agent:

```bash
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp
codex mcp add olmcp -- "$(which olmcp)" mcp
```

### 4. Ask for your first change

Select a sentence in Overleaf, leave a comment such as “make this clearer,” and tell the agent, with the project's id, URL, or Git URL:

> Address the review comments in https://www.overleaf.com/project/&lt;project-id&gt;

You can check your setup at any time with `olmcp doctor --project <project-id>`. If you would rather not name the project each time, run `olmcp init <project-id>` in a folder: it saves the project, the default mode, and an `AGENTS.md` there.

## Common tasks

| When you want to… | Do this |
|---|---|
| Request a change | Select text and leave an Overleaf Review comment |
| Apply an edit immediately | Add `#direct` to the comment (the default is a tracked change) |
| Ask the agent to focus on selected threads | Add `#agent` to those comments |
| Keep the agent away from a thread | Add `#no-agent` |
| Accept or reject an edit | Use Accept or Reject in the Review panel |
| Close a thread | Resolve it yourself; the agent never does |
| Undo a `#direct` edit | Use Overleaf History |

See [Use `olmcp`](docs/usage.md) for modes, comment tags, the tools, and settings.

## Documentation

- [Set up the connector](docs/setup.md)
- [Use comments, tags, and edit modes](docs/usage.md)
- [Connect Claude Code, Codex, or another agent](docs/agents.md)
- [Try the alpha on your own project](docs/alpha-test-plan.md)
- [Check current limitations and planned work](docs/status-and-roadmap.md)
- [Read the detailed design record](docs/design.md) (it also covers the earlier Python version)
- [Contribute to the project](CONTRIBUTING.md)

Release-by-release changes are listed in the [changelog](CHANGELOG.md). The earlier Python version (Git sync, `%% @agent:` markers, `redline.tex`, GitHub CI mode) lives on the [`python-legacy`](https://github.com/nipdep/agent-overleaf-connector/tree/python-legacy) branch.

## Credits and license

Apache 2.0. See [LICENSE](LICENSE). The Overleaf protocol handling follows the approach of [olcli](https://github.com/aloth/olcli) by Alexander Loth (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The tool uses Overleaf's unofficial web interface and your session cookie, so it can break when Overleaf changes; keep the cookie private.
