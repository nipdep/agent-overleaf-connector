# agent-overleaf-connector

Connect AI agents (Claude Code, Codex, any MCP client) to your **Overleaf** project. You comment in Overleaf's
Review panel; the agent reads your comments, edits the live document as **tracked changes** you accept or reject
in Overleaf, and replies in the same thread. Free, open source (Apache-2.0), one small Node program with no runtime
dependencies. No git, no CI, no copies of your paper.

```
 Overleaf project  ── your session cookie ──  olmcp (MCP server)  ──  AI agent
 (you comment here)                           comments · tracked edits · PDF    (Claude Code / Codex / ...)
```

- **Comments in, with the exact text.** Select a passage, comment; the agent gets your message, the selected
  text and the thread.
- **Edits out, in Reviewing mode.** The agent's change appears as a tracked deletion and insertion in the editor;
  its reply in the thread shows the word diff. Reject restores your text.
- **You stay in control.** The agent never resolves, closes or approves a thread (the tool has no such command).
  Optional hashtags steer it per comment: `#agent`, `#no-agent`, `#review` / `#suggest`, `#direct`.
- **See the result.** The agent can compile with Overleaf's own compiler and read the PDF.

> The command is `olmcp` (earlier versions were a Python tool of the same name, now on the `python-legacy` branch:
> uninstall it with `pipx uninstall agent-overleaf-connector` first).

> Status: early. Verified by the author on a real project with Claude Code and Codex (comments, tracked-change
> edits, replies, tags). See [docs/status-and-roadmap.md](docs/status-and-roadmap.md).

## Quick start

Needs Node 20+ and an Overleaf account. **No paid Overleaf plan, Git integration, clone or per-project setup is
needed.** One-time setup:

```bash
npm install -g github:nipdep/agent-overleaf-connector        # gives the command olmcp
olmcp auth --cookie "<value of the overleaf_session2 cookie>"   # never paste it into a chat
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp       # and/or:
codex mcp add olmcp -- "$(which olmcp)" mcp
olmcp doctor --project <project-id>                              # optional check
```

Then, from any folder, tell the agent which project, by id, project URL or the git URL Overleaf gives you:

> Address the review comments in https://www.overleaf.com/project/&lt;id&gt;

The agent passes the project to the tools itself. (Optional: `olmcp init <project-id>` in a folder saves the project,
the default mode and an `AGENTS.md` there, so you do not have to name it.) Details: [docs/setup.md](docs/setup.md).

## Everyday use

| You want to... | Do this |
|---|---|
| Ask for a change | Select text in Overleaf, add a Review comment |
| Have the agent skip a comment | Add `#no-agent` (the tools refuse it) |
| Focus the agent on a few comments | Add `#agent` to them; while any is open only those are listed |
| Choose how the edit is made | `#review` / `#suggest` (tracked change, default) or `#direct` (plain edit) |
| Accept or reject a change | The Review panel buttons in Overleaf |
| Close a thread | Resolve it yourself; the agent never does |

## Documentation

| | |
|---|---|
| [docs/setup.md](docs/setup.md) | Install, cookie, project, agents, troubleshooting |
| [docs/usage.md](docs/usage.md) | Comments, tags, modes, tools and commands |
| [docs/status-and-roadmap.md](docs/status-and-roadmap.md) | What is verified, open, planned |
| [docs/design.md](docs/design.md) | The design record, including the earlier Python version |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development and the real-Overleaf checklist |

The earlier Python version (git sync, `%% @agent:` markers, `redline.tex`, GitHub CI mode) lives on the
[`python-legacy`](https://github.com/nipdep/agent-overleaf-connector/tree/python-legacy) branch.

## Credits and licence

Apache-2.0. The Overleaf protocol handling follows the approach of [olcli](https://github.com/aloth/olcli) by
Alexander Loth (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). It relies on Overleaf's unofficial
web interface and your session cookie, so it can break when Overleaf changes; the cookie gives full access to your
account, so keep it private.
