# olmcp: design (v2)

An open-source toolkit for the review-and-revise loop on LaTeX papers when the editor is
Overleaf, the agent is an LLM, and neither can see the other's view of the paper.

Status tags used below: **[built]** exists and is tested, **[planned]** agreed, not built,
**[spike]** needs a quick experiment before it can be designed, **[unverified]** a claim about
something outside this repository that has not been tried.

---

## 0. What changed in v2

v1 was built around a flattened latexdiff redline and a CI pipeline. Working with the real
project showed what hurt, and these decisions replace v1's centre of gravity:

| # | Decision | Replaces |
|---|---|---|
| D1 | The **core needs only Python and git**. Rendering (TeX) and typeset redlines (Perl `latexdiff`) are optional layers. | TeX and latexdiff as hard requirements |
| D2 | **Changes are code diffs** from git, identified by content hashes, shown at word level. The diff is the authority. | latexdiff + a `git log -G` guess to attribute changes to commits |
| D3 | **The agent replies on the comment** for every change, so each comment holds the whole conversation (request, reply, decision, follow-up). | Comment-to-change mapping heuristics |
| D4 | **The paper is a dependency tree** found from a main file (`--main`, default `main.tex` at the root); only files in it are scanned, diffed and reviewed. | Scanning every `.tex` in the repo |
| D5 | **Review happens in a generated text file** (`review/REVIEW.md`); the typeset redline is optional. | `redline.tex` as the only review surface |
| D6 | **Local mode** is the primary transport: a clone of Overleaf's Git remote, `pull` before and `push` after an agent task. No daemon, no polling, no CI, no push/pull buttons. | CI + GitHub sync as the primary path |
| D7 | **Rendering has pluggable providers**: none, local TeX, CI mirror, Docker. | One build path |
| D8 | Linux and macOS first; Windows later (WSL2 as an interim route). | Cross-platform from day one |
| D10 | **Native Overleaf comments are supported** (select text in the Review panel), through the community CLI `olcli`. The `%%` marker stays as a no-dependency alternative. | `%%` markers as the only way to comment on a range of text |
| D9 | **The protocol is enforced by tools, not instructions.** An MCP server and `olmcp address` apply edits, write the reply, resolve, commit and handle branches atomically; the agent never runs git. | An `AGENTS.md` loop the agent had to follow step by step (a real agent pushed a branch to Overleaf and left the comment open) |

Not changed: git is the database, the CLI is the agent interface, comments are `%% @agent:`
marker lines typed in Overleaf, Apache-2.0, Python.

### Implementation status

| Area | Status |
|---|---|
| Build (`latexmk`, page PNGs, `text.json`), comment store, markers, `sync` | **[built]** |
| `direct` / `suggest` modes, `apply` (per comment), rollback tag, conflict rollback | **[built]** |
| Flattened latexdiff `redline.tex` (beside the main file) with `decision[...]` lines | **[built]** (becomes optional, see 8) |
| CI mode (reusable workflow, verified on real GitHub Actions) | **[built]** |
| Local mode: `pull` / `push`, `init --local` (tested against a bare repo imitating Overleaf) | **[built]** |
| Change log from `Resolves:` trailers | **[built]** |
| MCP server (`olmcp mcp`) and the atomic `olmcp address` for shell agents | **[built]**, tested with the SDK client, not yet inside Claude Code / Codex |
| ChatGPT web/desktop connector (remote MCP over HTTPS) | **[planned]**, blocked on an authentication decision (19) |
| Native Overleaf comments via `olcli`: import with selected text, replies and resolve written back, accept/reject by resolving or replying in the thread, project id automatic | **[built]**; import and replies confirmed by the user on a real project, thread decisions tested against a fake olcli only (20) |
| Optional rendering, `setup`, paper-aware `doctor` | **[planned]** |
| `--main`, dependency tree | **[planned]** |
| Diff-based changes, hunk ids, `REVIEW.md`, typed thread, reply gate | **[planned]** |
| CI mirror for renders (`renders`, `push --mirror`) | **[planned]** |
| Typeset redline: main file beside the real main, counterparts under `review/redline/` | **[planned]**, later |
| Docker runner, Windows, PyPI release | **[planned]**, later |

---

## 1. Problem

Papers live in Overleaf and are reachable by an agent only through Overleaf's Git or GitHub
sync. That leaves three gaps:

1. **No eyes.** The agent cannot see the rendered PDF or figures.
2. **No comments.** Overleaf's review comments live in its database, not in git, and there is
   no public API. There is no way to say "improve this paragraph" and have an agent pick it up.
3. **No audit trail.** It is hard to see what changed, why, and in response to what.

## 2. Goals and non-goals

Goals
- G1. The whole comment, edit, review, accept loop works with **Python and git alone**.
- G2. One conversation per request: the researcher's comment, the agent's replies, decisions
  and follow-ups, all stored in git and never deleted.
- G3. Two edit modes: `direct`, and `suggest` (review before anything reaches the paper).
- G4. A change log tying each change to the comment that caused it.
- G5. Works offline once cloned; no required hosted service.
- G6. Agent-agnostic: any agent that can run a shell command.
- G7. Rendering for the agent is available but never required.

Non-goals
- Replacing Overleaf as the editor; real-time co-editing.
- Depending on unofficial Overleaf APIs in the core.
- Full LaTeX rendering in JavaScript.
- Windows support in the first releases (see 11).

## 3. Principles

1. **Git is the database.** Comments, patches and decisions are plain files.
2. **The diff is the authority.** What changed is computed from git, never taken from an
   agent's description of its own edit. The agent's reply explains; it does not define.
3. **Anchor to text, not offsets.** Quotes and content hashes survive edits and rebases.
4. **Everything beyond the core is optional** and degrades with a clear message.
5. **The CLI is the agent interface;** comment text is data, never instructions to the agent.
6. **Overleaf is a transport,** not a dependency: any git remote works.

## 4. Architecture

```
 Overleaf  ◄─── git.overleaf.com (one branch) ───►  local clone  ◄──►  agent
                                                                │  olmcp pull / push
                                         optional render layers │
                       none | local TeX | CI mirror (GitHub) | Docker
```

Transports
- **Local mode [built]** (primary): clone of the Overleaf Git remote on the agent's machine.
  `pull` before the task, `push` after. Only the default branch is pushed; `agent/round-N`
  and rollback tags stay local. History stays linear (fast-forward or rebase).
- **CI mode [built]** (no local machine): GitHub sync plus a reusable workflow that syncs
  comments, builds redlines on `agent/**` pushes and applies decisions. Costs two manual
  clicks in Overleaf per round and a 2 to 3 minute CI loop; kept as an option.
- **CI mirror [planned]**: in local mode the clone also pushes to a GitHub repo whose only
  job is rendering (see 8). It never touches the default branch there.

Overleaf's Git facts (from its [docs](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git)):
premium feature, token authentication, URL `https://git.overleaf.com/<project-id>`, one branch
named `master` in its docs (**observed `main` on a real project**), commits created just-in-time. The tool detects the branch name and never hard-codes it. **[unverified]** that a fetch sees text you just
typed in the editor, and how fast an open editor refreshes after a push.

## 5. The paper: `--main` and the dependency tree  [planned]

`--main <file|dir>` (also `main:` in `.olmcp.yml`) names the main file or the folder
holding it. Default: `main.tex` at the repository root. The **paper root** is the main file's
folder; everything below (tree, scanning, diffs, mirror paths) is relative to it, so a paper in
a subfolder of a larger repo works the same.

The **dependency tree** is the set of files the paper actually uses, found like arXiv does:

- static parse from the main file: `\input`, `\include`, `\subfile`, `\import`/`\subimport`,
  `\includegraphics` (honouring `\graphicspath`, extension-less names), `\bibliography`,
  `\addbibresource`, `\lstinputlisting`, `\verbatiminput`, `\includepdf`, and local
  `.cls`/`.sty` files;
- when a build exists, `latexmk`'s `.fls` file lists every file TeX really read and corrects
  anything the static parse missed (paths hidden inside macros).

Uses: only tree files are scanned for markers and appear in diffs (this excludes the
`sample/` and `archive/` copies in the test project); the tree defines "the paper" for the
agent; `doctor --main paper/` prints which files are in and out so the researcher can check.

## 6. Comments and conversations

### 6.1 Writing a comment (in Overleaf)  [built]
```latex
%% @agent: soften this claim and add a citation
%% | (continuation lines start with "%% |")
Our method always outperforms the baselines.
```
A marker applies to the paragraph below it. A single `%` also works. Its identity is a hash of
file and text, so moving it does not duplicate it.

### 6.2 Follow-ups in the same thread  [planned]
```latex
%% @agent C-0001: no, keep the original wording here
```
A marker that names an existing id appends to that comment's thread instead of creating a new
comment, and reopens it if it was closed.

### 6.3 Comment file: `review/comments/C-0001.json`
`status`: `open` → `addressed` (agent changed it) → `resolved` (researcher accepted);
`wontfix`; `stale` **[planned]**: set when the quote can no longer be found.

The thread is **typed [planned]** (today entries are `author`, `at`, `body`):
```json
{ "type": "comment | reply | change | decision | follow-up",
  "author": "human:nipun | agent:claude", "at": "2026-11-03T10:12:00Z", "body": "...",
  "commit": "ab12cd3",            // change/reply entries
  "hunks": ["h-3f9a2c1e"],         // change entries
  "decision": "accept | reject" }  // decision entries
```
Nothing is ever deleted from a thread. A rejected change keeps its patch and its reason.

### 6.4 The agent must reply  [planned]
For each comment the agent (1) edits, (2) runs `olmcp reply C-0001 "what I changed and
why"`, (3) commits one comment per commit with `Resolves: C-0001`. The reply is a summary; the
diff (7) is the record. **Reply gate:** `push` refuses a `Resolves:` commit whose comment has
no agent reply, because agents do not reliably follow instructions they are not forced to.

## 7. Changes as diffs  [planned]

**Unit.** One commit per comment (as today). A commit's diff is split into **hunks**: a
contiguous changed region in one file of the dependency tree.

**Identity.** `hunk id = "h-" + first 8 hex of sha1(file, old text, new text)`, after
whitespace normalisation. It does not depend on line numbers or commit shas, so it survives
rebases (commit shas do not; that already broke decision carry-over in v1). `git patch-id`
gives the same stability for whole patches.

**Display.** LaTeX paragraphs are single long lines, so a line diff marks a whole paragraph.
Changed lines are shown at **word level**, e.g. `This creates [-an-]{+a genuine+} enforcement
dilemma.` (git's `--word-diff` or Python `difflib`; `diff-match-patch` is an alternative,
**[unverified]** as a better fit).

**Storage.** Each proposed change is saved as a patch so it stays readable and re-applicable
even after a reject or a rebase:
```
review/changes/C-0001/sections/03_model.tex.diff      same relative path as the source
```
**Binary files (figures).** A changed image is a binary change. The review lists
`figures/fig2.png: changed (old hash, new hash)`; optionally before/after copies are kept under
`review/changes/` so both open in Overleaf's file viewer. The agent's reply says what changed
inside the image. A comment placed above a figure block tells the agent where to look.

**Decisions** apply per comment, or per hunk when hunks are independent; overlapping or
dependent hunks fall back to the whole comment. Accept applies the patch to the default branch
(`git apply --3way` / cherry-pick) and adds a `decision` entry; reject adds a `decision` entry
with the reason and reopens the comment. A rollback tag is made first and a conflict undoes the
whole operation (as built today).

## 8. The review surface

### 8.1 `review/REVIEW.md`  [planned, default]
Generated; opened and edited in Overleaf's text editor. For every pending comment: the
researcher's request, the agent's reply, the word-level diff and decision lines:
```
## C-0001 · sections/03_model.tex:11
You: soften this claim and add a citation
Agent: Softened to "most baselines" and cited p_argos_onto; see hunk h-3f9a2c1e.
  - [-always outperforms the-]{+outperforms most+} baselines on all benchmarks
decision[C-0001]: pending           <- accept | reject
decision[C-0001/h-3f9a2c1e]: pending  (optional, per hunk)
reason[C-0001]:
```
No TeX, no Perl, no compile: works anywhere git works.

### 8.2 Typeset redline  [built as `redline.tex`, later optional]
Today: flattened `latexdiff` of base vs agent branch, written to `redline.tex` **beside the real main file**, with the same decision lines (needs
`latexdiff`; Overleaf compiles it). It stays as an optional layer.

Planned replacement, built on one invariant: **the redline's main file lives in the same folder
as the real main file** (the paper root; e.g. `<paper-root>/redline.tex`, name configurable).
Whatever way Overleaf resolves relative paths for the real main, it resolves them the same way
for the redline main, so `\includegraphics`, `\bibliography` and `\input` of unchanged files keep
working untouched. For each changed text file the tool writes a latexdiff-marked counterpart at
`review/redline/<same relative path>`, and the redline main `\input`s it by a path relative to
the paper root (`review/redline/sections/03_model`), the same base the paper's own relative
references use. No flattening, no copy of unchanged files or assets, and **no assumption about
Overleaf's path resolution**, so no probe is needed. Each counterpart starts with a visible stamp
as a cheap guard against compiling an unmarked original by mistake.

Status: the **invariant is built** for the flattened redline: `redline.tex` is written beside the
main file, new figures referenced as `review/assets/...` use the same base as the paper's own
references, and a pre-move `review/redline.tex` is removed on the next refresh (decisions typed
in it are carried over). Verified: it compiles from the repository root on the real 31-page
paper, figures and bibliography resolved. **[unverified]** inside Overleaf itself. The per-file
counterparts under `review/redline/` (no flattening) are still **[planned]**.

## 9. Modes and the loop

`mode: direct` commits on the current branch. `mode: suggest` works on a local
`agent/round-N`; nothing reaches the paper until the researcher accepts.

```
olmcp pull    # fetch the researcher's edits; sync markers; apply decisions; report
   agent: edit, reply on the comment, commit "Resolves: C-NNNN" (one comment per commit)
olmcp push    # refresh REVIEW.md (and optional redline), change log; publish the branch
```
`pull` reports what happened to every comment: new, reopened, removed by the researcher,
accepted, rejected with a reason. Both commands are idempotent and refuse a dirty tree. If the
researcher edited the paper while a branch is open, `pull` rebases the branch onto it and
regenerates the review file so it shows only the agent's changes. A conflict is reported and
nothing is changed. **[built]**, except `REVIEW.md` and hunk-level decisions.

The change log (`review/CHANGELOG.md`) is generated from `Resolves:` trailers, enriched with
the thread's reply. **[built]**, reply enrichment **[planned]**.

## 10. Rendering is optional  [planned]

The agent sees the paper only if a **render provider** is configured (`render:` in
`.olmcp.yml`, auto-detected otherwise):

| Provider | Needs | Notes |
|---|---|---|
| `none` (default if nothing found) | nothing | Everything except page images works. |
| `local` | TeX (`latexmk`) | `olmcp build`; page PNGs, `text.json`. **[built]** |
| `ci` | a GitHub repo as a mirror | `push --mirror` sends the default and agent branches to GitHub; the workflow runs in render-only mode (never touches the default branch there) and publishes PDF + PNGs to branch `olmcp/build`; `olmcp renders` fetches them. 2 to 3 minute latency, mostly the TeX Live image pull (caching unmeasured). |
| `docker` | Docker | Same toolchain on every OS; optional. |

Pin the TeX Live image to Overleaf's version: on the TGDK class, `texlive:latest` failed
(`Command \c@lemma already defined`) while `TL2025-historic` built it. **[built]** (workflow
input).

## 11. Installation, with reasons  [planned]

`olmcp setup` (and the README) list every dependency with why it is needed and what is
lost without it; it prints OS-specific commands and never runs `sudo` itself. `doctor` reports
each missing tool as "disables X", not as a failure, and `doctor --paper` checks the packages
the paper itself uses (`kpsewhich` against `\usepackage` and the class).

| Package | Needed for | If missing |
|---|---|---|
| Python ≥ 3.10, git | the whole core | cannot run |
| TeX: `latexmk`, fonts, packages | local page renders | agent cannot see layout |
| `latexdiff` (Perl) | the typeset redline only | review `REVIEW.md` instead |
| Docker | the Docker render provider only | use another provider |

Verified on Ubuntu (TeX Live 2023) for the TGDK paper: `latexmk latexdiff texlive-latex-base
texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended texlive-fonts-extra
texlive-plain-generic texlive-pictures texlive-science texlive-bibtex-extra texlive-publishers
cm-super lmodern`. `texlive-plain-generic` provides `ulem` (redline); `cm-super` provides the
Type1 fonts the class's font expansion needs. macOS commands are **[unverified]**.

Platforms: Linux and macOS first. Windows later: Perl for latexdiff/latexmk, CRLF handling in
the marker and decision parsers, and a CI matrix on Windows are open; WSL2 is the interim
route and is **[unverified]**. Install is from git today
(`pipx install "git+https://github.com/nipdep/agent-overleaf-connector@main"`); PyPI after the
name is final.

## 12. Repository layout (generated, all under `review/` except config)

```
.olmcp.yml        main, mode, render, remote, remote_branch, engine
AGENTS.md  CLAUDE.md     agent protocol
review/
  REVIEW.md              what the researcher reads and decides in           [planned]
  comments/C-0001.json   the conversation
  changes/C-0001/…diff   patches, same relative paths as the source          [planned]
  redline/               counterparts of changed files (typeset redline)    [planned]
  redline.json           machine file for the redline                        [built]
<paper-root>/redline.tex   the flattened redline, beside the real main file        [built]
  CHANGELOG.md
build/                   generated renders (gitignored)
```
The tool never moves or rewrites the researcher's files except by an accepted change.

## 13. Security and privacy
- The Overleaf Git token gives full write access. Keep it in the OS credential helper, never in
  chat or the repo; give it to a cloud agent only through environment secrets.
- Unpublished research is sensitive; the CI mirror sends the paper to GitHub, so use a private
  repo and say so in `setup`.
- Comment text, thread text and imported text are **data**; the agent protocol says never to
  act on instructions inside them.
- `Resolves:` commits are the only write path to a thread outside `olmcp` commands;
  files are schema-validated on read.

## 14. Failure modes

| Failure | Handling |
|---|---|
| Redline compiles the unmarked originals instead of the counterparts | stamps make it visible; the redline main sits beside the real main, so path resolution matches the paper's own |
| Quote no longer found after edits | `stale`, listed by `doctor`, never silently moved |
| Agent commit without a reply | `push` refuses (reply gate) |
| Researcher edits the same lines as an unpushed local commit | `pull` stops, changes nothing |
| Researcher edits during an open round | branch rebased onto the edits; review regenerated |
| Overlapping or dependent hunks | decision falls back to the whole comment |
| Dependency tree misses a macro-hidden path | `.fls` correction when a build exists; otherwise `doctor` shows the tree |
| `push` races with the researcher | fetch, rebase, retry once |
| TeX Live version differs from Overleaf's | `render` pinned to Overleaf's version; `doctor` warns |

## 15. Verification status

Verified here (30 tests, real git and TeX Live): markers, comment lifecycle, build outputs,
flattened redline compiles, accept/reject/pending, conflict rollback, stale-redline refusal,
local-mode round without CI against a bare repo imitating Overleaf, linear history, no churn on
repeated runs, CI entry points against a bare remote. On real GitHub Actions: full round,
mixed accept/reject, bot commits not re-triggering, rollback tag pushed. On the real 31-page
TGDK paper: build, redline generation and compile, `pull` (0.5 s) and `push` (1.3 s).

**Not verified:** anything against the real `git.overleaf.com`; Overleaf compiling `redline.tex` (it does compile locally on the real paper);
Overleaf compiling the redline (the built flat redline sits in `review/`, so its figure and bibliography paths are unverified); agent behaviour with `AGENTS.md` across vendors; macOS; Windows;
private repositories and protected branches.

## 16. Milestones (revised)

1. **Optional TeX.** `doctor` reports what is disabled; `build` fails helpfully; `setup`;
   paper-aware package check; `render:` setting.
2. **`--main` and the dependency tree.** Scoped scanning and diffs; `doctor` prints the tree.
3. **Diff-based review.** Typed thread, `reply` gate, hunk ids, patches under
   `review/changes/`, `REVIEW.md`, per-hunk decisions, follow-up markers.
4. **CI mirror renders.** Render-only workflow mode, `olmcp/build` branch, `renders`,
   `push --mirror`.
5. **Typeset redline mirror**, and move the redline main beside the real main.
6. **Platforms and release.** macOS check, Windows CI matrix, PyPI, optional Docker runner.

## 17. Open questions
1. ~~Overleaf path semantics~~ resolved by design: the redline main sits beside the real main (8.2).
2. Per-hunk decisions or per-comment only? Per-hunk is designed; start per-comment if simpler.
3. Final project name (repo is `agent-overleaf-connector`, CLI is `olmcp`).
4. Replace `latexdiff` with a Python diff to drop Perl entirely (riskier: latexdiff is careful
   with math and tikz); separate spike.
5. Real `git.overleaf.com` behaviour: edit visibility on fetch, editor refresh, acceptance of
   the generated files.
6. Whether `.fls` is always produced by the build providers (CI mirror yes; local yes).

## 18. Overleaf compatibility and plans

- **Native Overleaf comments are not in git.** Overleaf's own docs warn that pulling from
  GitHub can lose or displace tracked changes and comments, which is why comments are plain
  `%% @agent:` marker lines in the source: they live in the file and survive sync.
- **Plans.** Overleaf's Git integration and GitHub synchronization are premium features. Per
  Overleaf's docs, a free user invited to a project owned by a premium subscriber can use them
  inside that project. Institutional and group plans also include them.
- **Free routes without a premium owner [unverified]:** community bridges that use Overleaf's
  web API (for example olgitbridge) or a self-hosted Overleaf Community Edition. They are
  unofficial, depend on Overleaf internals and, for some, session cookies; treat them as
  best-effort and keep them out of the core.
- **Local mode** needs Overleaf's Git integration (clone URL and token); **CI mode** needs the
  GitHub sync. Either way the core never assumes more than "a git remote".
- **GitHub sync is manual** in both directions (Overleaf's push/pull buttons) and, as far as
  known, follows only the default branch **[unverified]**. Overleaf's Git has one branch,
  `master`, and no tags.

## 19. Agent connectors

**Why tools.** A real Claude Code run on the test project, without the CLI available, created
`agent/round-1`, edited the abstract, tried `git push origin agent/round-1` (Overleaf accepts only the
default branch: "wrong branch"), left the comment unresolved and asked what to do. Each step was
reasonable given the instructions, and all of it is mechanical. Handing the agent one operation that
does it all removes the failure surface.

**Tools [built].** `pull`, `list_comments`, `show_comment`, `read_file`, `list_paper_files`,
`address_comment(comment_id, edits[{file, old, new}], reply, commit_message?)`, `reply_to_comment`,
`push`, optional `build` and `view_page`. `address_comment` is all-or-nothing:
- every `old` must match exactly once (otherwise nothing is written; the message says how to retry);
- the comment's marker is removed, the reply recorded, status set (`resolved` in `direct`,
  `addressed` in `suggest`), and one commit created with the `Resolves:` trailer;
- in `suggest` mode the first call creates the local `agent/round-N` branch and later calls continue
  it; a failure deletes a branch it just created;
- paths are relative, inside the repository, only `.tex/.bib/.sty` are editable, `.git`, `build/` and
  `review/` are not; symlinks out of the repository are refused; there is no command-execution tool.
`olmcp address C-0001 edit.json` is the same operation for agents with only a shell.

**Error visibility.** The MCP SDK shows an agent only its own `ToolError`; any other exception is a
generic "Error executing tool", which would hide "old must match exactly once". The server translates
its refusals, and a test asserts the message reaches the client.

**Per client.** Claude Code: `.mcp.json` (project scope, user approves), `/address-comments`,
`CLAUDE.md` importing `AGENTS.md`. Codex: `codex mcp add`, `AGENTS.md`. Both start the server over
stdio. Other stdio clients: command `olmcp`, args `["mcp"]`.

**ChatGPT web/desktop [planned, undecided].** Per third-party documentation (not OpenAI's own pages,
**[unverified]**), custom connectors need a remote MCP endpoint over HTTPS, behind Developer Mode and a
plan that allows it, with OAuth or no authentication; they do not start local servers. Supporting it
means an HTTP transport plus making the local server reachable (a tunnel the user runs; the project
hosts nothing). The blocker is authentication: an unauthenticated public URL would give anyone write
access to the paper and, through `push`, the Overleaf credential in the credential helper. Options:
(a) implement a minimal single-user OAuth flow in the server (strongest, largest); (b) a
secret-in-URL path (simple, weak: URLs leak); (c) restrict to read-only tools for this client.
None is built. Until one is chosen, ChatGPT users use Codex.

**Not verified.** Behaviour inside Claude Code and Codex themselves (only the SDK's own client has
driven the server); whether agents reliably choose the tools over improvised git.

## 20. Native Overleaf comments  [built, unverified against the real service]

**Why.** `%%` markers cover a paragraph, not a selected range, and are clumsy to type. The experience
the researcher wants is Overleaf's own: select text, add a comment. Those comments live in Overleaf's
database, not in git, so the only route is the web editor's own API.

**How the existing tools do it** (read from their source, not tried): comment threads come from
`GET /project/<id>/threads` (messages), the commented text range from a Socket.IO `joinDoc` per file
(ranges with the thread id, position and text); writes are `POST .../thread/<id>/messages`
(`{content}`) and `POST .../doc/<doc>/thread/<id>/resolve|reopen`, with the session cookie and a CSRF
token read from the `/project` page. Two community implementations exist: **olcli** (MIT, Node CLI,
`comments list|reply|resolve|reopen|delete`) and netique's **overleaf-mcp** (AGPL-3.0, an MCP server).
We use olcli through its CLI: MIT is compatible with Apache-2.0, a subprocess keeps the licenses
separate, and re-implementing a Socket.IO 0.9 client blind, without a session to test against, would
be riskier than depending on a tool that already does it. netique's tool is not used (AGPL, MCP-only).

**Contract.** `olcli comments list <project-id> --status <s> --json` prints an array of
`{threadId, docId, path, position, line, column, selectedText, resolved, messages[{id, content,
timestamp, user}]}` (types from olcli's `client.ts`; the exact `--json` output is undocumented, so the
parser also accepts aliases and `{comments, changes}`). `reply <thread> <body> <project>`,
`resolve <thread> <project>`. Credentials stay with olcli (`OVERLEAF_SESSION` / `olcli auth`); this
tool never reads, stores or logs the cookie.

**Mapping.**
- `pull` imports each open thread as a comment: `origin = {type: overleaf, thread_id, doc_id}`,
  `body` = the first human message, `anchor.quote` = the selected text, `anchor.source` = file and line
  (olcli's line is trusted only if the quote is on it, otherwise the quote is searched in the file).
  Threads already resolved are not imported. Later human messages become thread entries and reopen a
  comment that was handled; resolving a thread in Overleaf resolves the local comment; deleting it
  marks the comment `wontfix`; reopening a thread we had resolved reopens the comment.
- **Telling the agent's messages apart.** Posted messages appear under the researcher's account, so every
  agent message is prefixed `[agent] ` and never imported as feedback.
- `push` (and `pull`, for accepted changes) **reconciles idempotently without local state**: an agent
  reply is posted only if no message with exactly that text is in the thread; a thread is resolved only
  if the local comment is `resolved` and it is still open there. In `suggest` mode replies are read from
  the agent branch's copy of the comment, so the researcher sees the reply before deciding; the thread is
  resolved only after the change is accepted.
- No marker exists for these comments, so there is nothing to remove from the source.

**Deciding in the thread [built].** The Review panel is also the accept/reject interface. When a change
for a comment is pending (it is in `redline.json`, and the agent has answered in the thread):
resolving the thread is an **accept**; a reply after the agent's message is a **reject**, and its text is
the instruction for the next attempt, unless it reads as an acceptance ("accept", "ok", "lgtm", a
thumbs-up; "reject: reason" gives an explicit reason). Resolving a thread when nothing is pending still just
closes the comment, and a thread resolved before the agent has answered counts for nothing. These decisions
are fed to the same `apply` as the `decision[...]` lines in `redline.tex`; a typed decision wins. The agent's
reply carries a one-line footer saying how to decide. Replies typed in Overleaf are not echoed back as
"Rejected: ..." entries (they are already in the thread).

**Merging comment files.** A researcher's reply (stored in the comment's JSON on the default branch) and the
agent's reply (stored in the same JSON on the agent branch) both edit one file, so accepting used to hit a
cherry-pick conflict. Conflicts confined to comment files are now merged (both conversations kept, the
agent's status wins because the acceptance follows, bookkeeping unioned); a conflict in the paper still
aborts and rolls back. The same applies when the agent branch is rebased onto the researcher's edits.

**Project id.** Read from the clone's remote URL (the host must mention overleaf, so a GitHub URL is never
mistaken for it; local paths are matched on the whole string for mirrors and tests). `overleaf_project`
overrides, `overleaf_comments: false` disables. With an auto-detected id and no `olcli` installed, `pull`
prints one line and carries on; an explicit id with a missing `olcli` is a warning.

**Failure handling.** Every olcli problem (missing binary, expired cookie, API change, timeout) becomes
a warning in `pull`/`push` and never blocks the git side. `overleaf-check` verifies access;
`overleaf-check --raw` prints olcli's JSON for diagnosing schema differences.

**Risks.** Unofficial API and a session cookie with full account access, stored in plain text by olcli
and expiring after days; `olcli auth --save-local` writes `.olauth` into the project (now gitignored by
`init`). Reading project documents for ranges is slow for large projects (olcli fetches every document;
each `reply`/`resolve` re-lists). Tracked changes are a separate, premium-dependent feature and unused here.

**Not verified.** Everything against the real olcli and Overleaf: the actual JSON, that `line` and
`selectedText` match a git clone's content, that replies render as expected, olcli's behaviour when
given a project id positionally for `reply`/`resolve` (its source says a 24-hex id is accepted).

## 21. The agent's edits as Overleaf tracked changes  [investigated, not built]

**Wanted.** Suggestions as tracked changes ("Reviewing" mode) in `main.tex` itself, next to the comments,
and in direct mode a plain edit.

**Direct mode already is a plain edit:** the agent commits, `push` goes to Overleaf's Git, and the file
changes in place.

**Findings for Reviewing mode** (read from sources, not tried):
- **olcli cannot author tracked changes.** Its `tracked-changes.ts` only lists them and rejects them (OT ops
  carrying the editor's undo flag); there is no accept path and nothing that creates a suggestion.
- **Git cannot create them either.** Overleaf's docs say pushes from Git can lose or displace tracked
  changes and comments and recommend not mixing active Git use with track changes and comments.
- **The only known writer** is netique's `overleaf-mcp` (AGPL-3.0, an MCP server, Chrome-based login): it
  sends edits over the editor's live Socket.IO channel (`applyOtUpdate`) with track-change metadata.
  Using it means running it as a separate process (license stays separate) or a clean-room implementation of
  the write path, which cannot be verified without a live session and can corrupt a document if the OT ops
  are wrong.

**What is unknown, and decides the design.** (1) What a git clone shows for a file that holds pending tracked
changes: are tracked deletions still in the text? Both versions of a sentence side by side would break our
whole git-based flow. (2) Whether `olmcp push` of other files, or the next `pull`, disturbs pending
suggestions or comment anchors.

**Consequence if built.** The model flips for files with pending suggestions: Overleaf is the source of
truth, the agent edits through the live channel, git is pull-only for those files, and `apply` /
cherry-picks / the local agent branch are replaced by Overleaf's own accept and reject (observed through
`olcli comments list --changes`). A different architecture for suggest mode, not an add-on.

**Decision.** Not built. Interim, shipped in 0.7.0: the proposed edit appears inside the comment thread as a
word diff, so comment and change are together and accept/reject is already in the Review panel (section 20).

**Experiment that would settle the unknowns** (on a scratch copy of a project, with netique's tool): make a
suggestion with `edit_file` (`track: on`); look at it in the editor; `git pull` and read the file; push an
unrelated change and re-check the suggestion and a comment anchor.

## 22. Redline annotations  [built]

`redline.tex` used to put one block ("C-0005 - <commit subject>", the decision lines) above the first change of
a comment and a bare "change continues" above the others, so the reader could not tell which words a decision
was about. Every change location now gets a note: the comment id, "change i of n", the real file and line
(found with `git grep` in the version where the change lives, so it points into the file that is `\\input`,
not into the flattened redline), `asked:` (the comment's text), and `edit:` (a one-line word diff cropped to
the changed words plus some context). The decision lines still sit with the first change and say how many
changes they decide; later changes name the decision that covers them.

The word diff compares words, LaTeX commands and single punctuation marks, never whitespace, and keeps the
original spacing (an earlier version diffed whitespace tokens and produced scrambled output such as
`in{+one+} [-a long-]`). latexdiff leaves doubled spaces where it substitutes text, so the file search
normalises whitespace first. The same helper produces the diff shown in Overleaf comment threads (20).
