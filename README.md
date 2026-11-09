<p align="center">
  <img src="docs/assets/olmcp-logo.png" alt="Agent standing over a leaf" width="220">
</p>

# Agent–Overleaf Connector (`olmcp`)

[![tests](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml)  [![M8ven Score](https://m8ven.ai/badge/mcp/nipdep/agent-overleaf-connector)](https://m8ven.ai/mcp/nipdep/agent-overleaf-connector?s=readme) 

[![Overleaf for AI agents (olmcp) MCP server](https://mcprush.com/badge/overleaf-for-ai-agents-olmcp/card.svg)](https://mcprush.com/to/overleaf-for-ai-agents-olmcp?ref=badge)


`olmcp` lets an AI agent respond to review comments in an Overleaf project.

You comment in Overleaf. The agent reads the comment and the selected text, proposes an edit as an Overleaf tracked change, and replies in the same thread. You remain the reviewer: you accept or reject the edit and close the thread.

`olmcp` has no hosted backend: the connector runs on your computer and uses your Overleaf session. Your chosen AI client may still send MCP results to its model provider under that client's own privacy terms.

## The workflow

```text
1. You select text and leave a comment in Overleaf.
2. The agent reads the comment and the live project.
3. The agent proposes a tracked change and replies in the thread.
4. You accept, reject, request another version, or resolve the thread.
```

By default, an edit is a **proposal**, not a silent replacement. Overleaf shows the original text as a tracked deletion and the proposed text as a tracked insertion.

> **Project status:** `1.0.0-alpha.3`. The core review flow has been used on real Overleaf projects; newer features such as pending-suggestion revision and file creation still need real-service testing. Start with a disposable project.

## What the MCP can and cannot do

| It can | It deliberately cannot |
|---|---|
| Read comments, threads, selected text, and text files in the project | Accept or reject a tracked change for you |
| Propose tracked edits in `review` mode | Resolve, reopen, close, or delete a comment thread |
| Apply a plain edit when you explicitly use `#direct` | Overwrite or delete an existing file |
| Reply in a comment thread | Edit documents that use Overleaf's unsupported newer history format |
| Revise its own pending suggestion when you ask for another version | Create images, PDFs, or other binary project files |
| Create a new text file and missing folders | Work continuously in the background or watch for new comments |
| Compile the project on Overleaf and save the PDF locally | Give the agent a separate Overleaf identity; changes use your account |

The tool surface enforces these limits. However, an agent with unrestricted shell access could read the stored session cookie and contact Overleaf outside the MCP. See [Security and trust](docs/agents.md#security-and-trust).

## Quick start

You need Node.js 20 or newer, an Overleaf account, and an MCP-capable agent such as Claude Code or Codex. You do **not** need Python, TeX, or Overleaf's paid Git integration. The current GitHub-based installation may also need the `git` command; normal use does not.

### 1. Install `olmcp`

```bash
npm install -g github:nipdep/agent-overleaf-connector
olmcp --version
```

### 2. Sign in to Overleaf

Copy the `overleaf_session2` cookie from your browser's developer tools, then run:

```bash
olmcp auth --cookie "<cookie value>"
```

Treat this cookie like a password. Never paste it into an agent chat, issue, or commit. The [setup guide](docs/setup.md#2-sign-in-to-overleaf) shows where to find it and what to do when it expires.

### 3. Register the MCP server

Choose your agent, then restart it:

```bash
# Claude Code
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp

# Codex
codex mcp add olmcp -- "$(which olmcp)" mcp
```

Windows PowerShell commands and other MCP clients are covered in [Connect an AI agent](docs/agents.md).

### 4. Give the agent your project URL

No project folder or clone is required. After connecting the MCP, paste the Overleaf project URL into the request:

> Address the comments in https://www.overleaf.com/project/&lt;project-id&gt;.

If you prefer not to paste the URL each time, you can save the project ID in a working folder with `olmcp init`. See [Choosing a project](docs/setup.md#4-choose-how-to-name-the-project).

### 5. Address a comment

In Overleaf, select a sentence and comment “make this clearer.” Then tell your agent:

> Address the comments in https://www.overleaf.com/project/&lt;project-id&gt;.

Back in Overleaf, review the tracked edit. Accept or reject it, reply with another request, or resolve the thread yourself.

## Everyday controls

| When you want to… | Do this in Overleaf |
|---|---|
| Propose a normal reviewable edit | Leave an ordinary comment; `review` is the default |
| Apply an edit without tracked changes | Add `#direct` to the comment |
| Keep the agent away from a thread | Add `#no-agent` |
| Focus the agent on particular threads | Add `#agent` to those comments |
| Ask for another version of a pending suggestion | Reply in the same thread, for example “shorter please,” then run the agent again |
| Add a new section or bibliography file | Ask in a comment; the new file appears immediately, while the `\input` or bibliography edit is proposed separately |
| Finish a discussion | Resolve the thread yourself |

Read [Using `olmcp`](docs/usage.md) for examples, modes, tags, file creation, and the complete MCP tool list.

## Important safety details

- Tracked changes are attributed to your Overleaf account because the connector uses your session.
- A newly created file cannot be a tracked change. It appears immediately; the connector never overwrites or deletes files.
- `#direct` changes are immediate. Use Overleaf History if you need to undo one.
- The interface is unofficial and may break when Overleaf changes it.
- The session cookie usually expires after a few days. Run `olmcp auth` again when `olmcp doctor` reports an expired session.

## Documentation

- [Start here: documentation map](docs/README.md)
- [Install and set up](docs/setup.md)
- [Use comments, proposals, tags, and files](docs/usage.md)
- [Connect and constrain an AI agent](docs/agents.md)
- [Run the alpha test checklist](docs/alpha-test-plan.md)
- [Check verified behavior and current limits](docs/status-and-roadmap.md)
- [Understand the technical design](docs/design.md)
- [Contribute](CONTRIBUTING.md)

Release changes are in the [changelog](CHANGELOG.md). The retired Python workflow—Git sync, source markers, `redline.tex`, and GitHub Actions—remains on the [`python-legacy`](https://github.com/nipdep/agent-overleaf-connector/tree/python-legacy) branch.

Logo files: [PNG](docs/assets/olmcp-logo.png) · [SVG](docs/assets/olmcp-logo.svg)

## License and credit

Apache 2.0. See [LICENSE](LICENSE). The Overleaf protocol handling follows the approach used by [olcli](https://github.com/aloth/olcli) by Alexander Loth (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
