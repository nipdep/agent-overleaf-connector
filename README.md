<p align="center">
  <img src="docs/assets/olmcp-logo.png" alt="Agent standing over a leaf" width="220">
</p>

# Agent–Overleaf Connector (`olmcp`)

[![tests](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/nipdep/agent-overleaf-connector/actions/workflows/ci.yml)

`olmcp` lets an AI coding agent work on your Overleaf paper without taking you out of the review loop. You leave a comment in Overleaf; the agent reads it with its selected text, edits the paper as **tracked changes** you accept or reject, and replies in the same thread. Open source (Apache 2.0); nothing is hosted for you.

- **Ask where you already work.** Select text and leave a normal Review comment.
- **Review where you already review.** The agent's edit appears as a tracked deletion and insertion with Accept and Reject buttons. Reject restores your text.
- **Steer per comment, optionally.** `#direct` applies an edit immediately, `#no-agent` keeps the agent away, `#agent` focuses it on selected threads.
- **You close the threads.** The agent replies in plain words but never resolves, closes, or approves a thread; the tool has no such command.
- **Any MCP agent.** Claude Code, Codex, or any client that can start a local MCP server. The agent can also compile the project with Overleaf's compiler and read the PDF.

> **Status:** 1.0.0-alpha.1. Used by the author with Claude Code and Codex on a real project, and covered by automated tests; it relies on Overleaf's unofficial web interface and needs wider testing. Want to help? See the [alpha test plan](docs/alpha-test-plan.md) and [Status and roadmap](docs/status-and-roadmap.md).

## Set up (once per computer)

You need **Node.js 20 or newer** and an Overleaf account. No Python, Git, TeX, or paid Overleaf plan is required, and nothing runs in the background. Everything heavy (reading, tracking changes, compiling) happens on Overleaf's servers, so the program is not tied to an operating system (tested on Linux and macOS; Windows is untested).

```bash
npm install -g github:nipdep/agent-overleaf-connector        # 1. install
olmcp auth --cookie "<overleaf_session2 cookie value>"          # 2. sign in (never paste the cookie into a chat)
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp       # 3. connect your agent (restart it afterwards)
codex mcp add olmcp -- "$(which olmcp)" mcp                     #    ...or Codex
```

Where to find the cookie, and troubleshooting: [setup guide](docs/setup.md).

## Connect a project (pick one)

- **A. Just use the project URL.** Nothing to set up. You paste the URL when you ask (see below).
- **B. Work from a clone.** If you want a local folder per paper, clone it with the Git command Overleaf shows (**Menu → Sync → Git**, a premium feature) and start the agent in that folder:

  ```bash
  git clone https://git@git.overleaf.com/<project-id> my-paper && cd my-paper
  ```

  `olmcp` finds the project from the clone, so you never have to name it. The agent's edits still go into the live Overleaf project, not the clone (`git pull` to catch up).

`olmcp doctor --project <project-id>` checks that everything works.

## Use it (every time)

1. In Overleaf, select text and leave a comment such as “make this clearer.”
2. Tell your agent, in its chat or from the command line:

   > Address the review comments.

   With option A, add the project: *“Address the review comments in https://www.overleaf.com/project/&lt;project-id&gt;”*. To run it without opening a chat, use your agent's one-shot mode, for example `claude -p "Address the review comments"` or `codex exec "Address the review comments"`.
3. Back in Overleaf, accept or reject each tracked change, reply in the thread, or resolve it.

That is the whole loop. Setup never has to be repeated, except to refresh the cookie when it expires after a few days.

## Common tasks

| When you want to… | Do this |
|---|---|
| Request a change | Select text and leave an Overleaf Review comment |
| Apply an edit immediately | Add `#direct` to the comment (the default is a tracked change) |
| Ask the agent to focus on selected threads | Add `#agent` to those comments |
| Keep the agent away from a thread | Add `#no-agent` |
| Ask for a new file (a section, a bibliography) | Say so in a comment; the agent creates it with `create_file` and adds the `\input` line as a tracked change |
| Ask for another version of a suggestion | Reply in the thread ("shorter please"); the agent updates the suggestion in place, no need to accept or reject first |
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
- [Read how it works and why](docs/design.md) (the earlier Python design is kept in [docs/history](docs/history/design-python.md))
- [Contribute to the project](CONTRIBUTING.md)

Release-by-release changes are listed in the [changelog](CHANGELOG.md). The earlier Python version (Git sync, `%% @agent:` markers, `redline.tex`, GitHub CI mode) lives on the [`python-legacy`](https://github.com/nipdep/agent-overleaf-connector/tree/python-legacy) branch.

Logo files are available as [PNG](docs/assets/olmcp-logo.png) and [SVG](docs/assets/olmcp-logo.svg).

## Credits and license

Apache 2.0. See [LICENSE](LICENSE). The Overleaf protocol handling follows the approach of [olcli](https://github.com/aloth/olcli) by Alexander Loth (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The tool uses Overleaf's unofficial web interface and your session cookie, so it can break when Overleaf changes; keep the cookie private.
