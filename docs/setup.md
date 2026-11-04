# Setup

The connector currently supports Linux and macOS. Windows is not supported yet; WSL2 may work, but has not been tested.

## Before you begin

| You need | Why |
|---|---|
| Node.js 20 or later, on Linux, macOS or Windows | Running `olmcp`. Nothing else: no Python, no Git, no TeX |
| An Overleaf account and project | Comments, tracked changes, the PDF. **Git integration is not needed** |
| Claude Code, Codex or another MCP client | The agent |

> **Platforms.** Nothing in the program is OS-specific: it speaks HTTPS to Overleaf and everything else (reading files,
> compiling, the diff) happens on Overleaf's servers. CI runs the tests on Linux and macOS. Windows is not tested yet;
> the one command in this guide that is bash syntax is `"$(which olmcp)"`, which in PowerShell is
> `(Get-Command olmcp).Source`, and the 0600 permission on the cookie file has no effect there, so keep your user
> folder private.

## 1. Install

```bash
npm install -g github:nipdep/agent-overleaf-connector
olmcp help
```

This installs from GitHub into npm's own location, so it keeps working if you move your folders. To update, run
the same command again. To work from a clone instead: `git clone ... && cd agent-overleaf-connector && npm install -g .`
(the install is a link to that folder: do not move or delete it afterwards).

## 2. Sign in with your session cookie

Overleaf has no public API for comments, so the tool uses the same web interface your browser uses. In your
browser's developer tools open Application, Cookies, your Overleaf site, and copy the value of `overleaf_session2`:

```bash
olmcp auth --cookie "<paste cookie value here>"
```

It is stored in `~/.config/olmcp/config.json` (mode 0600), or give it in `OVERLEAF_SESSION`. For a
self-hosted Overleaf add `--base-url https://your.overleaf.example`. The cookie gives full access to your account and
expires after a few days; repeat this step when the tool says the session expired. Never paste it into a chat, an
issue or a commit. If you did, log out of Overleaf in the browser (that ends the session) and sign in again.

## 3. Connect your agent (once)

```bash
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp
codex mcp add olmcp -- "$(which olmcp)" mcp
```

These register the server for all your folders; restart the agent afterwards. Other MCP clients that start local
servers: command `olmcp`, argument `mcp`. ChatGPT's chat apps need a remote HTTPS server and are not supported; use
Codex. (Claude Code without `--scope user` registers it for the current folder only.)

## 4. Name the project

Nothing needs to be cloned or configured per project. Either tell the agent the project when you ask:

> Address the review comments in https://www.overleaf.com/project/&lt;id&gt;

(the id, the project URL or the git URL all work; the tools take a `project` argument and the server's own instructions
tell the agent to pass it), or save it for a folder:

```bash
mkdir my-paper-agent && cd my-paper-agent
olmcp init <project-id> --mode review        # or --mode direct
olmcp doctor
```

`init` writes `.olmcp.json` (project and default mode) and an `AGENTS.md` with the agent's instructions (an existing
`AGENTS.md` is left alone). Without it the same instructions come from the server itself. A folder that is a clone of the
project's Overleaf git remote is recognised too, and `--project` / `OVERLEAF_PROJECT` also work.

## 5. Use it

Comment in Overleaf, then tell the agent "address the review comments". It lists the comments, edits the live
document as tracked changes, replies in each thread, and leaves the threads open for you.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `olmcp --version` or `olmcp help` shows the old Python tool (`pull`, `mode`, ...) | The Python version is still installed and first on your `PATH`: `pipx uninstall agent-overleaf-connector` (and `pipx uninstall paper-review` if present), then open a new shell |
| `doctor` says the session expired or the cookie is missing | Run `olmcp auth --cookie ...` again |
| The agent says the executable is missing | The global link points at a moved or deleted folder: reinstall (step 1), then `codex mcp remove olmcp` and add it again with the new `which olmcp` |
| The agent still behaves like an old version | A running agent keeps its server process: quit it completely and start it again |
| `the old text appears more than once` / `was not found` | The edit's `old` text must match exactly once; the agent should read the file again and use a longer passage |
| `already carries a tracked change` | Accept or reject the existing change in Overleaf first |
| `newer document format` | That document uses Overleaf's newer history format, which cannot be edited yet |
| The edit lands but is not tracked | The client reports it; check Overleaf's History and send the message with an issue |
