# agent-overleaf-connector (`olmcp`)

A review-and-revise loop for LaTeX papers written in **Overleaf**, edited by an **AI agent**
(Claude, ChatGPT/Codex, anything that can use git), with a **redline** you can accept or
reject, and a **change log**. Open source (Apache-2.0), no hosted service: it runs on GitHub
Actions and on your own machine.

> Status: v0.1, built from [docs/design.md](docs/design.md). The core is tested; the GitHub
> workflow and the Overleaf round trip have **not** been run against real GitHub / Overleaf
> yet (see [What is verified](#what-is-verified)).

## The problem

Overleaf exposes your project only through its Git/GitHub sync. Over that path an agent can't
see the rendered paper, can't read your comments (Overleaf comments live in its database, not
in git), and you get no clear record of what changed and why.

## How it works

```
Overleaf ──push──► GitHub repo ──► CI: build PDF, sync comments, redline, apply decisions
   ▲                                   │
   └─────────────pull──────────────────┘            agent: reads comments, edits, commits
```

1. **Comment** in Overleaf with a plain marker line before a paragraph. No tooling needed, and
   it survives GitHub sync (native Overleaf comments can be displaced by it):
   ```latex
   %% @agent: soften this claim and cite a source
   Our method always outperforms the baselines.
   ```
2. **Push to GitHub.** CI turns markers into comments (`review/comments/C-0001.json`).
3. **The agent** (given the repo and `AGENTS.md`) builds the paper, looks at the page images,
   edits the .tex, and commits one comment per commit with a `Resolves: C-0001` trailer.
   - `mode: direct` commits on your branch.
   - `mode: suggest` pushes `agent/round-N`; CI writes **`redline.tex`** next to `main.tex`.
4. **Review the redline inside Overleaf**: set `redline.tex` as the main document (Menu → Settings → Main document).
   Next to each change are lines like
   ```
   %% decision[C-0001]: pending      <- type accept or reject
   %% reason[C-0001]:                <- optional; goes back to the agent
   ```
   Edit them, push to GitHub. CI cherry-picks the accepted commits, drops the rejected ones
   (their comments reopen with your reason), tags a rollback point, and regenerates the redline
   with what is still pending. Pull in Overleaf. Real undo is git history, not the editor.
5. `review/CHANGELOG.md` is generated from the trailers: what changed, why, and where.

## Local mode: Overleaf Git, no CI, no push/pull buttons (recommended)

Overleaf also runs its own Git server (a premium feature, separate from the GitHub sync). A clone
of it on the machine where the agent runs removes the CI wait and the manual buttons. There is
no daemon and no polling; the agent wraps its task in two commands:

```
olmcp pull   # before: fetch the researcher's edits and report what happened to the comments
   ... agent edits, commits on a local agent/round-N branch ...
olmcp push   # after: refresh redline.tex + change log, publish the branch to Overleaf
```

1. In Overleaf: Menu → Sync → Git shows the clone URL (`https://git.overleaf.com/<project-id>`);
   create a Git token in your Overleaf account settings. Let your git credential helper store
   it; never paste it into a chat or commit it.
2. `git clone https://git.overleaf.com/<project-id> paper && cd paper`
3. `olmcp init --local --mode suggest`, review the files, commit, then `olmcp push`.
4. Per round: you type `%% @agent: ...` markers in Overleaf (nothing to press: Overleaf's Git
   server creates a commit from your latest edits when the clone fetches). The agent runs `pull`,
   works, and runs `push`. In Overleaf you open `redline.tex` (set it as main document),
   type `accept` / `reject` on the `%% decision[...]` lines, and carry on. The next `pull`
   applies your decisions and reports them.

Behaviour worth knowing:
- Only the default branch is pushed (Overleaf's Git has a single branch; its docs call it `master`, your project may show `main`); the
  `agent/round-N` branch stays local, as do the rollback tags.
- History stays linear (fast-forward or rebase, never a merge commit). If the researcher edited
  the same lines as a local unpushed commit, `pull` stops and changes nothing.
- If you edit the paper in Overleaf while an agent branch is open, `pull` rebases the branch
  onto your edits and regenerates the redline so it only shows the agent's changes.
- `pull` / `push` are idempotent: repeated runs create no new commits.

Verified here against a bare git repository that imitates Overleaf's remote (a single
branch, a second clone playing the researcher): the full round without CI, conflicts, a push
that races with the researcher, and no churn on repeated runs. **Not verified against the real
`git.overleaf.com`**: that a clone sees edits you just made in the editor, how quickly the open
editor refreshes after a push, and whether Overleaf accepts the redline and comment files.

## Native Overleaf comments: select text, comment, done

Instead of typing `%%` markers you can use Overleaf's own Review panel: select a range, add a
comment, and the agent sees your message **and the exact selected text**. Its reply shows up in the
same Overleaf thread (prefixed `[agent]`), and the thread is resolved when the change is accepted.
This is optional and uses the community CLI [olcli](https://github.com/aloth/olcli) (MIT), because
Overleaf has no public API for comments and they are not in git.

1. `npm install -g @aloth/olcli`
2. Log in with your Overleaf **session cookie**: in your browser's developer tools open Application →
   Cookies → `overleaf.com` and copy the value of `overleaf_session2`, then run
   `olcli auth --cookie "<value>"` (or set `OVERLEAF_SESSION`). Never paste it into a chat. It gives full
   access to your account, `olcli` stores it in plain text, and it expires after a few days (repeat this
   step when `pull` warns about a session).
3. That's all the setup. The project id is read from your clone's Overleaf URL automatically (override
   with `overleaf_project:`, turn the feature off with `overleaf_comments: false`).
4. Check it: `olmcp overleaf-check` should print `ok: project …: N thread(s) …`.

Then comment in Overleaf as usual and run `pull`; the comments appear with their selected text.

**Deciding in the thread.** In `suggest` mode the agent's reply in the thread says the change is only
proposed. Then, right in the Review panel:

- **Resolve the thread (the check mark): accept.** The change is applied to your paper.
- **Reply: reject or adjust.** Your reply is the instruction for the agent's next attempt. A reply that
  says "accept", "ok", "lgtm" or gives a thumbs-up accepts instead; "reject: reason" rejects with that reason.

The agent's reply in the thread includes **the edit itself** as an inline word diff
(`Our method [-always-] outperforms [-the-]{+most+} baselines`), labelled "Proposed edit" (suggest mode) or
"Edit applied" (direct mode). So the comment, the change and the accept/reject controls are all in the Review
panel. In direct mode the agent edits your file in place (a normal Overleaf edit), nothing to accept.

Typing `accept` / `reject` on the `decision[...]` lines in `redline.tex` still works and wins if the two
disagree. `redline.tex` remains the place to see the change as a typeset redline.
`%%` markers keep working alongside. Resolving or deleting a thread in Overleaf is mirrored, and a
follow-up you write there reopens the comment for the agent.

Verified here against a **fake `olcli`** that follows the documented command shapes (import, selected
text, follow-ups, replies, resolving in both edit modes, failures as warnings). **Not verified against
the real `olcli` and Overleaf yet**: its exact JSON for `comments list --json` is undocumented, so the
parser accepts the documented field names and aliases; if `overleaf-check` fails, run
`olmcp overleaf-check --raw` and send me the output with the names and emails removed.

## Use it from Claude Code, Codex and other AI tools

You should only have to say **"address the review comments"**. The tool does the git work, so
the agent never creates branches, writes commit trailers or pushes anything itself.

Install with the MCP extra:

```bash
pipx install --force "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"
```

- **Claude Code:** `claude mcp add olmcp -- olmcp mcp` (or approve the project's
  `.mcp.json` when asked), then say "address the review comments" or type `/address-comments`.
  `CLAUDE.md` imports `AGENTS.md`, so the protocol is always loaded.
- **Codex** (CLI, IDE, app): `codex mcp add olmcp -- olmcp mcp`. It reads `AGENTS.md`.
- **Other clients that start local MCP servers** (Claude Desktop, Cursor, ...): command
  `olmcp`, args `["mcp"]`, run from the clone (or pass `--root <clone>`).
- **No MCP?** Shell agents use `olmcp pull`, `olmcp address C-0001 edit.json`
  (edits + reply + commit in one atomic step, branches handled for you) and `olmcp push`.

The tools: `pull`, `list_comments`, `show_comment`, `read_file`, `address_comment`,
`reply_to_comment`, `push`, plus optional `build` / `view_page`. `address_comment` applies your edits
(each `old` text must match exactly once), removes the comment's marker, records the reply,
resolves the comment and commits with the `Resolves:` trailer, all or nothing. Paths are confined to
the repository; there is no tool that runs arbitrary commands.

**ChatGPT chat (web/desktop connectors) is not supported yet.** Per third-party documentation,
ChatGPT's custom connectors need a remote HTTPS MCP server (Developer Mode, plan-dependent, OAuth or
no auth) and cannot start a local one. Exposing this server would put write access to your paper
and your Overleaf credentials behind a public URL, so it needs an authentication design first.
Codex, OpenAI's coding agent, works today through the same MCP server and `AGENTS.md`.

Verified: the real server driven over stdio by the MCP SDK's own client (tool list, a full
address-and-push round, error messages reaching the agent). **Not yet verified:** inside Claude Code
or Codex themselves.

## CI mode: GitHub sync (no local machine needed)

### Setup (researcher)

1. In Overleaf: Menu → GitHub, create the repository. (Overleaf's GitHub/Git sync is a
   premium feature; see [docs/design.md](docs/design.md#18-overleaf-compatibility-and-plans) for
   free-plan routes.)
2. On github.com add `.github/workflows/olmcp.yml` (the 10-line file `olmcp init`
   generates, or copy [the template](src/olmcp/templates/workflow.yml)).
   On its first run CI adds `.olmcp.yml`, `AGENTS.md`, `CLAUDE.md` and `review/`.
3. In Overleaf click *Pull from GitHub* once.
4. Give your agent the repository; it reads `AGENTS.md` / `CLAUDE.md`. It needs push access to
   create `agent/round-N` branches.

You never need to run the CLI yourself.

## CLI (agents, CI, offline use)

```
olmcp init [--mode suggest]   add config, workflow, agent instructions
olmcp build                   PDF + build/pages/*.png + build/text.json + synctex
olmcp sync                    markers -> comments
olmcp list|show|reply|resolve comment operations (all support --json)
olmcp round                   next agent/round-N name
olmcp redline <branch>        write redline.tex (beside the main file)
olmcp apply                   apply accept/reject decisions
olmcp changelog               write review/CHANGELOG.md
olmcp pull / push             local mode: wrap an agent task (see above)
olmcp ci [--push]             what the workflow runs (CI mode)
olmcp doctor                  check environment
```

Install: `pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@main"` (from a checkout: `pip install -e .[mcp]`; not on PyPI yet; if you had the old `paper-review` install, run `pipx uninstall paper-review` first). It needs
`latexmk` and `latexdiff` (TeX Live) on the PATH, or use `docker/Dockerfile`, the same
toolchain as CI. Offline use is just `olmcp build` on a clone.

## What is verified

Unit and integration tests (`pytest`, 89 tests, real git and real TeX Live): marker parsing,
comment lifecycle, build outputs (PDF, page PNGs, text boxes), redline generation and that it
**compiles to a PDF**, change attribution to commits, accept / reject / pending, conflict
rollback, stale-redline refusal, asset handling, change log, and the CI entry points against a
real bare remote.

**On real GitHub Actions** (a sandbox branch with a demo paper, 6 runs): the reusable workflow
resolves from another branch; the `texlive/texlive` image runs the install, build and artifact
upload; the bot pushes sync / redline / decision / change-log commits with `[skip ci]` and does
not re-trigger itself; a full round works: markers become comments, an `agent/round-N` push
produces `redline.tex`, and `accept` / `reject` (with a reason) pushed back are applied,
the rejected comment reopens, the agent branch is deleted and the pre-apply rollback tag is
pushed. A run takes about 1.5 to 2 minutes, mostly pulling the TeX Live image.

**Not verified**, so treat as unproven until tried on a scratch project:
- Overleaf compiling `redline.tex` as a main document and syncing the generated files back
  (it compiles with a plain TeX Live on the real 31-page paper, figures and bibliography
  included; it sits beside `main.tex`, so Overleaf resolves its paths as it does the paper's);
- whether Overleaf's GitHub sync follows only the default branch;
- agent behaviour with `AGENTS.md` across vendors;
- private repositories (Actions minutes) and branch protection on the default branch.

## Match Overleaf's TeX Live version

Overleaf's compiler and TeX Live version are project settings that are not stored in git, and
they matter: on the TGDK journal class, `texlive/texlive:latest` failed with
`Command \c@lemma already defined` while an older TeX Live built it. Set the image in the
caller workflow to match Overleaf (Menu → Settings → TeX Live version):

```yaml
jobs:
  review:
    uses: nipdep/agent-overleaf-connector/.github/workflows/review.yml@main
    with:
      texlive_image: texlive/texlive:TL2025-historic
```

## Known limits

- Overleaf's compiler and TeX Live version are project settings that are not in git; set
  `engine` in `.olmcp.yml` if you don't use pdfLaTeX (`doctor` warns).
- Change attribution to commits is heuristic (matches each changed line to the commit that
  produced it); unattributed changes are labelled and can't be decided separately.
- Decisions are per commit (per comment), not per hunk.
- Not implemented yet: the local viewer/server, importing native Overleaf comments or PDF
  annotations, SyncTeX click-to-source, automatic `stale` detection. See the design doc.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]' && pytest
```

License: Apache-2.0.
