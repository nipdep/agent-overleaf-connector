# Set up the connector

This guide takes you from installation to your first agent-assisted edit.

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

## 3. Connect your agent

```bash
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp
codex mcp add olmcp -- "$(which olmcp)" mcp
```

These register the server for all your folders; restart the agent afterwards. Other MCP clients that start local
servers: command `olmcp`, argument `mcp`. ChatGPT's chat apps need a remote HTTPS server and are not supported; use
Codex. (Claude Code without `--scope user` registers it for the current folder only.)

## 4. Connect a project (pick one)

Nothing needs to be configured per project. You can name the project in one of two ways.

**Option A: give the agent the project URL (no clone).** Start the agent in any folder and say:

> Address the review comments in https://www.overleaf.com/project/&lt;id&gt;

The project id, the project URL, and the Git URL all work. The tools take a `project` argument, and the server's own
instructions tell the agent to pass it. This works on any Overleaf plan.

**Option B: clone the project and work from the clone.** Use the Git command Overleaf gives you (Menu, Sync, Git; a
premium feature):

```bash
git clone https://git@git.overleaf.com/<project-id> my-paper
cd my-paper
olmcp doctor
```

Start the agent in that folder. `olmcp` reads the project id from the clone's Git remote (only when the remote's host
is an Overleaf server), so you can just say "Address the review comments." The agent's edits still go into the live
Overleaf project, not the clone: run `git pull` to bring the clone up to date, and have the agent read the paper
with the `read_file` tool so it sees the live text.

**Saving the project for a folder.** In either option, `olmcp init <project-id> --mode review` (or `--mode direct`) in a
folder writes `.olmcp.json` (project and default mode) and an `AGENTS.md` with the agent's instructions. An existing
`AGENTS.md` is left alone. Without it, the same instructions come from the server itself. `--project` and the
`OVERLEAF_PROJECT` variable also name a project.

## 5. Use it (every time)

Steps 1 to 3 are one-time setup per computer, and step 4 is only about how the agent learns the project. From then on
the loop is:

1. Comment in Overleaf.
2. Tell the agent, in its chat or from the command line: "Address the review comments." (With option A, add the
   project URL.) For a command-line one-shot, use your agent's non-interactive mode, for example
   `claude -p "Address the review comments"` or `codex exec "Address the review comments"`.
3. Accept or reject the tracked changes in Overleaf, and resolve the threads yourself.

The agent lists the comments, edits the live document as tracked changes, replies in each thread, and leaves the
threads open for you. Only the cookie ever needs refreshing (it expires after a few days).

## Update to the latest version

New features arrive on the `main` branch. To get them:

```bash
npm uninstall -g olmcp
npm install -g github:nipdep/agent-overleaf-connector#main
olmcp --version
```

If the version did not change, npm is reusing a cached copy of the branch. Clear it and try again
(`npm cache clean --force`), or install a specific commit, which can never be served from an older cache:
`npm install -g github:nipdep/agent-overleaf-connector#<commit>`. Then **quit your agent completely and start it
again**: a running agent keeps the old server until it restarts, so new tools such as `create_file` appear only after
that. Your cookie and the agent registration stay valid; `which -a olmcp` should list a single `olmcp`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `olmcp --version` or `olmcp help` shows the old Python tool (`pull`, `mode`, ...) | The Python version is still installed and first on your `PATH`: `pipx uninstall agent-overleaf-connector` (and `pipx uninstall paper-review` if present), then open a new shell |
| A new feature or tool is missing after updating | The agent is still running the old server (restart it completely), or npm served a cached copy: see [Update to the latest version](#update-to-the-latest-version) |
| `doctor` says the session expired or the cookie is missing | Run `olmcp auth --cookie ...` again |
| The agent says the executable is missing | The global link points at a moved or deleted folder: reinstall (step 1), then `codex mcp remove olmcp` and add it again with the new `which olmcp` |
| The agent still behaves like an old version | A running agent keeps its server process: quit it completely and start it again |
| `the old text appears more than once` / `was not found` | The edit's `old` text must match exactly once; the agent should read the file again and use a longer passage |
| `already carries a tracked change` | Accept or reject the existing change in Overleaf first |
| `newer document format` | That document uses Overleaf's newer history format, which cannot be edited yet |
| The edit lands but is not tracked | The client reports it; check Overleaf's History and send the message with an issue |
