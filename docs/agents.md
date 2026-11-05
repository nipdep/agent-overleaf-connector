# Connect an AI agent

`olmcp` is the bridge between your agent and Overleaf. It handles the connection, the edits, and the thread replies; the agent focuses on reading and editing the paper. `olmcp mcp` is a local MCP server (stdio) that the agent client starts. See [setup](setup.md) for the two
registration commands; the tools are listed in [usage](usage.md).

| Client | Registration | Notes |
|---|---|---|
| Claude Code | `claude mcp add --scope user olmcp -- "$(which olmcp)" mcp` | Restart it after adding; `--scope user` makes it available in every folder |
| Codex | `codex mcp add olmcp -- "$(which olmcp)" mcp` | Reads the folder's `AGENTS.md` |
| Others that start local servers | command `olmcp`, arguments `mcp` | Untested |
| ChatGPT chat apps | not supported | They need a remote HTTPS server with authentication |

Name the project when you ask (the tools take a `project` argument: id, project URL or git URL), or run the agent
from a folder where you ran `olmcp init`, which holds the project id and an `AGENTS.md`. Keep any older MCP server for the same project removed, so the agent has one set of tools.

## Behaviours worth knowing

- **Revising.** When you answer a suggestion with "try again", the agent calls `address_comment` again with the suggested
  text as the old text, and the suggestion changes in place (see [Use `olmcp`](usage.md#ask-for-another-version-without-accepting-or-rejecting)).
- **New files.** The agent creates a file with `create_file` and uses it with an `address_comment` edit. File creation
  is immediate and untracked; the tool never overwrites or deletes (see [creating new files](usage.md#creating-new-files)).
- **New tools need a restart.** An agent keeps the tool list it started with, so after updating `olmcp`, restart it.

## Safety rules enforced by the connector

Enforced in code: edits validated before anything is written, `#no-agent` refusal, the researcher's tag beating the
agent's mode, no way to resolve, reopen or delete a thread. Only instruction (in `AGENTS.md`, which you can
edit): how to word replies, when to ask instead of guess, "do not use another way to reach Overleaf".

An agent with a shell can still read your cookie file or call Overleaf by other means; the tool does not claim to
prevent that. If you want to reduce the risk, deny shell access to `olmcp` and `~/.config/olmcp`
in your agent's permission settings (Claude Code: `permissions.deny` such as `Bash(olmcp:*)`; the MCP server is
unaffected). Codex has command rules for the same purpose; check its documentation for the syntax.
