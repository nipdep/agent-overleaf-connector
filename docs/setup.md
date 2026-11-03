# Setup

## What you need

| Needed | For |
|---|---|
| Node.js 20 or later | Running `olmcp` |
| An Overleaf account and project | Comments, tracked changes, the PDF. **Git integration is not needed** |
| Claude Code, Codex or another MCP client | The agent |

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

## 3. Point a folder at the project

The project id is the 24-character part of the project's URL.

```bash
mkdir my-paper-agent && cd my-paper-agent
olmcp init <project-id> --mode review        # or --mode direct
olmcp doctor
```

`init` writes `.olmcp.json` (project and default mode) and an `AGENTS.md` with the agent's instructions
(an existing `AGENTS.md` is left alone). `doctor` must show the cookie present and the comments readable. The project
is also found from `--project`, `OVERLEAF_PROJECT`, or the git remote of the folder if it is an Overleaf clone.

## 4. Connect your agent

Run these from the folder, then restart the agent:

```bash
claude mcp add olmcp -- "$(which olmcp)" mcp
codex mcp add olmcp -- "$(which olmcp)" mcp
```

Other MCP clients that start local servers: command `olmcp`, argument `mcp`, working directory the folder.
ChatGPT's chat apps need a remote HTTPS server and are not supported; use Codex.

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
