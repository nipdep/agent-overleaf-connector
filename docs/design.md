# paper-review: design (v2)

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

Not changed: git is the database, the CLI is the agent interface, comments are `%% @agent:`
marker lines typed in Overleaf, Apache-2.0, Python.

### Implementation status

| Area | Status |
|---|---|
| Build (`latexmk`, page PNGs, `text.json`), comment store, markers, `sync` | **[built]** |
| `direct` / `suggest` modes, `apply` (per comment), rollback tag, conflict rollback | **[built]** |
| Flattened latexdiff `review/redline.tex` with `decision[...]` lines | **[built]** (becomes optional, see 7) |
| CI mode (reusable workflow, verified on real GitHub Actions) | **[built]** |
| Local mode: `pull` / `push`, `init --local` (tested against a bare repo imitating Overleaf) | **[built]** |
| Change log from `Resolves:` trailers | **[built]** |
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
 Overleaf  ◄─── git.overleaf.com (one branch: master) ───►  local clone  ◄──►  agent
                                                                │  paper-review pull / push
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
named `master`, commits created just-in-time. **[unverified]** that a fetch sees text you just
typed in the editor, and how fast an open editor refreshes after a push.

## 5. The paper: `--main` and the dependency tree  [planned]

`--main <file|dir>` (also `main:` in `.paper-review.yml`) names the main file or the folder
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
For each comment the agent (1) edits, (2) runs `paper-review reply C-0001 "what I changed and
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

### 8.2 Typeset redline  [built as `review/redline.tex`, later optional]
Today: flattened `latexdiff` of base vs agent branch with the same decision lines (needs
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

Known gap in what is built today: `review/redline.tex` sits in a subfolder and rewrites paths of
newly added figures to `review/assets/...`, which assumes Overleaf resolves from the project
root. Compiling that file in Overleaf, especially its figures and bibliography, is
**[unverified]**; moving the redline main beside the real main removes the question.

## 9. Modes and the loop

`mode: direct` commits on the current branch. `mode: suggest` works on a local
`agent/round-N`; nothing reaches the paper until the researcher accepts.

```
paper-review pull    # fetch the researcher's edits; sync markers; apply decisions; report
   agent: edit, reply on the comment, commit "Resolves: C-NNNN" (one comment per commit)
paper-review push    # refresh REVIEW.md (and optional redline), change log; publish master
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
`.paper-review.yml`, auto-detected otherwise):

| Provider | Needs | Notes |
|---|---|---|
| `none` (default if nothing found) | nothing | Everything except page images works. |
| `local` | TeX (`latexmk`) | `paper-review build`; page PNGs, `text.json`. **[built]** |
| `ci` | a GitHub repo as a mirror | `push --mirror` sends the default and agent branches to GitHub; the workflow runs in render-only mode (never touches the default branch there) and publishes PDF + PNGs to branch `paper-review/build`; `paper-review renders` fetches them. 2 to 3 minute latency, mostly the TeX Live image pull (caching unmeasured). |
| `docker` | Docker | Same toolchain on every OS; optional. |

Pin the TeX Live image to Overleaf's version: on the TGDK class, `texlive:latest` failed
(`Command \c@lemma already defined`) while `TL2025-historic` built it. **[built]** (workflow
input).

## 11. Installation, with reasons  [planned]

`paper-review setup` (and the README) list every dependency with why it is needed and what is
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
.paper-review.yml        main, mode, render, remote, remote_branch, engine
AGENTS.md  CLAUDE.md     agent protocol
review/
  REVIEW.md              what the researcher reads and decides in           [planned]
  comments/C-0001.json   the conversation
  changes/C-0001/…diff   patches, same relative paths as the source          [planned]
  redline/               counterparts of changed files (typeset redline)    [planned]
  redline.tex, redline.json   current flattened redline                     [built]
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
- `Resolves:` commits are the only write path to a thread outside `paper-review` commands;
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

Verified here (27 tests, real git and TeX Live): markers, comment lifecycle, build outputs,
flattened redline compiles, accept/reject/pending, conflict rollback, stale-redline refusal,
local-mode round without CI against a bare repo imitating Overleaf, linear history, no churn on
repeated runs, CI entry points against a bare remote. On real GitHub Actions: full round,
mixed accept/reject, bot commits not re-triggering, rollback tag pushed. On the real 31-page
TGDK paper: build, redline generation and compile, `pull` (0.5 s) and `push` (1.3 s).

**Not verified:** anything against the real `git.overleaf.com`;
Overleaf compiling the redline (the built flat redline sits in `review/`, so its figure and bibliography paths are unverified); agent behaviour with `AGENTS.md` across vendors; macOS; Windows;
private repositories and protected branches.

## 16. Milestones (revised)

1. **Optional TeX.** `doctor` reports what is disabled; `build` fails helpfully; `setup`;
   paper-aware package check; `render:` setting.
2. **`--main` and the dependency tree.** Scoped scanning and diffs; `doctor` prints the tree.
3. **Diff-based review.** Typed thread, `reply` gate, hunk ids, patches under
   `review/changes/`, `REVIEW.md`, per-hunk decisions, follow-up markers.
4. **CI mirror renders.** Render-only workflow mode, `paper-review/build` branch, `renders`,
   `push --mirror`.
5. **Typeset redline mirror**, and move the redline main beside the real main.
6. **Platforms and release.** macOS check, Windows CI matrix, PyPI, optional Docker runner.

## 17. Open questions
1. ~~Overleaf path semantics~~ resolved by design: the redline main sits beside the real main (8.2).
2. Per-hunk decisions or per-comment only? Per-hunk is designed; start per-comment if simpler.
3. Final project name (repo is `agent-overleaf-connector`, CLI is `paper-review`).
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
