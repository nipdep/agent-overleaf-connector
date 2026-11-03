# Connecting an AI agent

`olmcp mcp` is a local MCP server (stdio) that the agent client starts. See [setup](setup.md) for the two
registration commands; the tools are listed in [usage](usage.md).

| Client | Registration | Notes |
|---|---|---|
| Claude Code | `claude mcp add --scope user olmcp -- "$(which olmcp)" mcp` | Restart it after adding; `--scope user` makes it available in every folder |
| Codex | `codex mcp add olmcp -- "$(which olmcp)" mcp` | Reads the folder's `AGENTS.md` |
| Others that start local servers | command `olmcp`, arguments `mcp` | Untested |
| ChatGPT chat apps | not supported | They need a remote HTTPS server with authentication |

Name the project when you ask (the tools take a `project` argument: id, project URL or git URL), or run the agent
from a folder where you ran `olmcp init`, which holds the project id and an `AGENTS.md`. Keep any older MCP server for the same project removed, so the agent has one set of tools.

## What the tools enforce, and what is only instruction

Enforced in code: edits validated before anything is written, `#no-agent` refusal, the researcher's tag beating the
agent's mode, no way to resolve, reopen or delete a thread. Only instruction (in `AGENTS.md`, which you can
edit): how to word replies, when to ask instead of guess, "do not use another way to reach Overleaf".

An agent with a shell can still read your cookie file or call Overleaf by other means; the tool does not claim to
prevent that. If you want to reduce the risk, deny shell access to `olmcp` and `~/.config/olmcp`
in your agent's permission settings (Claude Code: `permissions.deny` such as `Bash(olmcp:*)`; the MCP server is
unaffected). Codex has command rules for the same purpose; check its documentation for the syntax.
