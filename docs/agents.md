# Connecting an AI agent

`olmcp-overleaf mcp` is a local MCP server (stdio) that the agent client starts. See [setup](setup.md) for the two
registration commands; the tools are listed in [usage](usage.md).

| Client | Registration | Notes |
|---|---|---|
| Claude Code | `claude mcp add olmcp-overleaf -- "$(which olmcp-overleaf)" mcp` | Restart it after adding |
| Codex | `codex mcp add olmcp-overleaf -- "$(which olmcp-overleaf)" mcp` | Reads the folder's `AGENTS.md` |
| Others that start local servers | command `olmcp-overleaf`, arguments `mcp` | Untested |
| ChatGPT chat apps | not supported | They need a remote HTTPS server with authentication |

Run the agent from the folder where you ran `olmcp-overleaf init`: it holds the project id and `AGENTS.md`.
Keep any older MCP server for the same project removed, so the agent has one set of tools.

## What the tools enforce, and what is only instruction

Enforced in code: edits validated before anything is written, `#no-agent` refusal, the researcher's tag beating the
agent's mode, no way to resolve, reopen or delete a thread. Only instruction (in `AGENTS.md`, which you can
edit): how to word replies, when to ask instead of guess, "do not use another way to reach Overleaf".

An agent with a shell can still read your cookie file or call Overleaf by other means; the tool does not claim to
prevent that. If you want to reduce the risk, deny shell access to `olmcp-overleaf` and `~/.config/olmcp-overleaf`
in your agent's permission settings (Claude Code: `permissions.deny` such as `Bash(olmcp-overleaf:*)`; the MCP server is
unaffected). Codex has command rules for the same purpose; check its documentation for the syntax.
