# Setting up a new Overleaf project

Supported: Linux and macOS. Windows is not supported yet (WSL2 may work, untested).

## What you need

| Needed | For |
|---|---|
| Python 3.10+, `git`, `pipx` | Everything |
| An Overleaf project with **Git integration** (a premium feature; a free account can use it inside a project owned by a premium user) | Reaching the project |
| Node.js 20+ and the `olmcp-overleaf` command (in `node/` of this repository) | Native Overleaf comments and tracked-change edits. Optional: `%%` markers work without it |
| `latexdiff` | The typeset redline in `suggest` mode only |
| TeX Live (`latexmk` and packages) | Only for local page renders (`olmcp build`). Optional |

`olmcp doctor` reports what is present and what each missing tool would disable.

## 1. Install

```bash
pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"
olmcp --version
```

If you had the tool under its old name, run `pipx uninstall paper-review` first (both would provide a
`paper-review` command; the old name still works as an alias for now).

Optional parts:

```bash
git clone https://github.com/nipdep/agent-overleaf-connector ~/agent-overleaf-connector
(cd ~/agent-overleaf-connector/node && npm install -g .)   # native Overleaf comments: gives olmcp-overleaf
sudo apt install -y latexdiff       # redline for suggest mode (macOS: brew install latexdiff)
```

## 2. Credentials

Never paste either of these into a chat, an issue or a commit.

**Overleaf Git token** (to clone, pull and push): Overleaf, Account settings, Git integration, create a token.
Keep it in memory only instead of letting git write it to disk:

```bash
git config --global credential.helper 'cache --timeout=14400'
```

(`store` also works but saves the token in plain text in `~/.git-credentials`, readable by any program you
run, including an agent.)

**Overleaf session cookie** (for `olmcp-overleaf`, native comments only): in your browser's developer tools open
Application, Cookies, `overleaf.com`, and copy the value of `overleaf_session2`:

```bash
olmcp-overleaf auth --cookie "<paste cookie value here>"
```

This cookie gives full access to your Overleaf account. It is stored in `~/.config/olmcp-overleaf/config.json`
(mode 0600, outside any project) and it expires after a few days. When `olmcp pull` warns about a session,
repeat this step. If you ever pasted it into a chat, log out of Overleaf in the browser (that ends the session)
and sign in again for a new one.

Check the client on its own first:

```bash
olmcp-overleaf check <project-id>      # ok: N comment thread(s) readable
```

## 3. Clone the project

The project id is the 24-character part of its URL. Username is `git`, password is your token.

```bash
git clone https://git@git.overleaf.com/<project-id> ~/Dev/my-paper
```

If it hangs with no password prompt, you are probably in VS Code's terminal, where git's credential prompt
appears as a small box at the top of the window. To prompt in the terminal instead:

```bash
env -u GIT_ASKPASS -u SSH_ASKPASS GIT_TERMINAL_PROMPT=1 git clone https://git@git.overleaf.com/<project-id> ~/Dev/my-paper
```

The first clone of a large project can take minutes.

## 4. Set it up in the clone

Pick the default mode (you can change it any time with `olmcp mode`, and per comment with a tag):

- `direct`: the agent edits your files in place and replies in the comment thread. Nothing to accept.
- `suggest`: the agent's changes wait for you to accept or reject them.

```bash
cd ~/Dev/my-paper
olmcp init --local --mode direct
olmcp doctor
olmcp overleaf-check
git add -A && git commit -m "Set up olmcp" && olmcp push
```

`init` adds (nothing existing is overwritten):

| File | Purpose |
|---|---|
| `.olmcp.yml` | Settings (mode, main file, ...) |
| `AGENTS.md`, `CLAUDE.md` | The protocol agents follow (`CLAUDE.md` imports `AGENTS.md`) |
| `.mcp.json`, `.claude/commands/address-comments.md` | Claude Code: the MCP server entry and the `/address-comments` command |
| `review/README.md` | A note for you inside the project |
| `.gitignore` entries | `build/` and `.olauth` |

After `olmcp push` these files appear inside your Overleaf project; that is expected.

Checks:

- `doctor` shows your main file. If it picked the wrong one, set `main: path/to/main.tex` in `.olmcp.yml`.
  A `latexmk` FAIL line is fine unless you want local renders.
- `overleaf-check` should print `ok: project ...: N thread(s) ...`. The project id comes from the clone's URL;
  you never type it anywhere.

## 5. Connect an agent

From inside the clone. Restart the agent afterwards (a running session does not pick up new servers).

```bash
claude mcp add olmcp -- "$(which olmcp)" mcp      # Claude Code
codex mcp add olmcp -- "$(which olmcp)" mcp       # Codex
```

More in [agents.md](agents.md).

## 6. First test

1. In Overleaf, select a sentence, open Review and add a comment such as "make this shorter".
2. In the clone run `olmcp pull`. Expect `Overleaf comments: 1 thread(s) checked: 1 created` and an
   `on: "<your selected text>"` line.
3. Tell the agent: **"address the review comments"** (Claude Code: `/address-comments`).
4. In Overleaf's thread you will see the agent's reply with the edit as `[-removed-]{+added+}`. In `direct`
   mode the file is already changed. In `suggest` mode resolve the thread to accept, or reply to reject, then
   run `olmcp pull && olmcp push`.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Clone hangs with no prompt | VS Code's credential helper; use the second clone command above |
| `Authentication failed` / 403 on clone | Wrong or revoked token, or Git integration not available for that project (premium) |
| `pull` prints `Overleaf comments: off (...)` | The remote is not an Overleaf URL, or `olmcp-overleaf` is not installed; the message says which |
| `Overleaf client ... failed` or a session warning | The cookie expired: run `olmcp-overleaf auth --cookie ...` again |
| `pull` finds no threads you can see | Run `olmcp overleaf-check --raw` and look at what the client returns (remove names and emails before sharing it) |
| The agent says it has no tools | Run `claude mcp list` / `codex mcp list`, restart the agent, and check `which olmcp` in the terminal the agent uses; use the full path from `which olmcp` in the `mcp add` command |
| `error: ... needs the optional 'mcp' extra` | Reinstall with `[mcp]`, as in step 1 |
| `redline.tex` is empty or has no changes | The agent's commit changed files the paper does not use, or only comments; the redline lists a `WARNING` with the files |
| Build fails in CI with a LaTeX error inside a journal class | The CI TeX Live version differs from Overleaf's; see [ci-mode.md](ci-mode.md) |
| A change you made in Overleaf is not seen | Overleaf's Git creates a commit when the clone fetches; run `olmcp pull` again |

Still stuck: open an issue using the bug template, with `olmcp --version` and `olmcp doctor` output, and no
tokens or cookies.
