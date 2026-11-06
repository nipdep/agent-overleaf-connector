# Set up the connector

This guide takes you from a fresh computer to one reviewable agent edit in Overleaf.

The recommended path is:

```text
install → sign in → register the MCP → paste a project URL → try one comment
```

## Before you begin

You need:

- Node.js 20 or newer.
- An Overleaf account and a project you can edit.
- Claude Code, Codex, or another client that can start a local MCP server.
- The `git` command if npm needs it to install this alpha from GitHub. `olmcp` itself does not use Git.

You do not need Python, a local TeX installation, or Overleaf's paid Git integration. `olmcp` works with the live Overleaf project.

## 1. Install `olmcp`

```bash
npm install -g github:nipdep/agent-overleaf-connector
olmcp --version
```

The command should print the current alpha version. To update later, run the same `npm install -g` command again and restart your agent so it starts the new MCP server.

If `olmcp --version` shows the retired Python program, remove it first:

```bash
pipx uninstall agent-overleaf-connector
pipx uninstall paper-review
```

Then open a new terminal and install again with npm.

## 2. Sign in to Overleaf

Overleaf does not provide a public API for comments and tracked changes. `olmcp` therefore uses the same session as your browser.

### Find the cookie

1. Sign in to Overleaf in your browser.
2. Open a project.
3. Open the browser's developer tools.
4. Find the cookies for `https://www.overleaf.com`:
   - Chrome or Edge: **Application → Storage → Cookies**.
   - Firefox: **Storage → Cookies**.
5. Copy the value of `overleaf_session2`.

Store it with:

```bash
olmcp auth --cookie "<cookie value>"
```

The cookie is saved in `~/.config/olmcp/config.json` with user-only permissions on Linux and macOS. It gives access to your Overleaf account, so treat it like a password:

- Never paste it into an agent chat, issue, screenshot, or commit.
- Be aware that the command may remain in your shell history.
- If it is exposed, sign out of Overleaf in the browser, sign in again, and store the new cookie.
- When it expires after a few days, repeat this step.

For a self-hosted installation, add `--base-url https://overleaf.example`. You can also provide the cookie through `OVERLEAF_SESSION` instead of saving it.

## 3. Register the MCP server

Choose the client you use.

### Claude Code

```bash
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp
claude mcp list
```

### Codex

```bash
codex mcp add olmcp -- "$(which olmcp)" mcp
codex mcp list
```

Restart the client after registration. The client starts `olmcp mcp` when needed; no background service should be running.

On Windows PowerShell, replace `"$(which olmcp)"` with `(Get-Command olmcp).Source`. More client-specific details are in [Connect an AI agent](agents.md).

## 4. Choose how to name the project

Every MCP call needs an Overleaf project. Choose one of these approaches.

### Easiest: paste the project URL into the request

No project folder or clone is required. Start the agent anywhere and say:

> Address the comments in https://www.overleaf.com/project/&lt;project-id&gt;.

The project ID, project URL, and Overleaf Git URL are accepted by the MCP tools. Include one whenever the agent cannot infer the project from saved configuration.

To check the connection first, run:

```bash
olmcp doctor --project <project-id>
```

### Optional: save the project ID in a folder

Take the 24-character ID from the project's URL, create or enter a working folder, and run:

```bash
mkdir my-paper-agent
cd my-paper-agent
olmcp init <project-id> --mode review
olmcp doctor
```

This writes:

- `.olmcp.json`, containing the project ID and default edit mode.
- `AGENTS.md`, containing the recommended instructions for the agent, unless the folder already has one.

It does not download or modify the paper. Start the agent in this folder and say, “Address the comments.” Because the project is saved, you no longer need to include its URL.

If you already have a Git clone of the Overleaf project, you may run `olmcp init` inside it. The MCP still reads and edits the live Overleaf project; the local clone can be behind.

### Other configuration choices

For automation, `--project <id>` and `OVERLEAF_PROJECT` can provide the project. The normal setup does not need them.

## 5. Make a safe first test

Use a disposable Overleaf project for the first run.

1. Select one sentence in Overleaf and leave the comment “make this shorter.”
2. In the agent, say “Address the comments in `<project URL>`.”
3. Confirm that Overleaf shows a tracked deletion and insertion.
4. Confirm that the thread contains an `[agent]` reply and remains open.
5. Click **Reject** and confirm that the original sentence returns.

The [alpha test plan](alpha-test-plan.md) covers tags, PDFs, pending-suggestion revisions, subfolders, and new files.

## Check the installation

With a pasted-URL workflow, pass the project ID explicitly. If you saved the project with `olmcp init`, the shorter command is enough:

```bash
olmcp doctor --project <project-id>  # no saved project
olmcp doctor                         # inside a configured folder
```

A healthy result reports:

- Node 20 or newer.
- A stored session cookie.
- The chosen project and default mode.
- Successful access to Overleaf comment threads.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `olmcp` is not found | Open a new terminal after installation. If it still fails, check npm's global binary directory is on `PATH` |
| The old Python commands (`pull`, `push`, `mode`) appear | Uninstall the pipx packages shown in step 1, then reinstall with npm |
| `doctor` reports a missing or expired session | Repeat step 2 with a current `overleaf_session2` cookie |
| The MCP client cannot start `olmcp` | Remove and re-add the MCP entry using the current result of `which olmcp` or `Get-Command olmcp` |
| The agent behaves like an older release | Fully restart it; a running client may still have the old MCP process |
| No project is set | Run `olmcp init <project-id>` in the working folder, or include the project URL in the request |
| `old` text was not found or appears more than once | The agent must call `read_file` again and use a longer exact passage |
| The text already carries a tracked change | Accept or reject that change first, unless you are asking the agent to revise its own pending insertion |
| A document uses the newer history format | Reading may work, but editing is currently refused rather than attempted unsafely |
| An edit appears untracked when review mode was requested | Check Overleaf History and report the error; the connector should fail loudly instead of claiming success |

Still stuck? Include `olmcp --version`, `node --version`, your operating system, your MCP client, and the redacted output of `olmcp doctor` in the report. Never include the session cookie, private document text, names, or email addresses.
