# paper-review

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
   - `mode: suggest` pushes `agent/round-N`; CI writes **`review/redline.tex`**.
4. **Review the redline inside Overleaf**: set `review/redline.tex` as the main document.
   Next to each change are lines like
   ```
   %% decision[C-0001]: pending      <- type accept or reject
   %% reason[C-0001]:                <- optional; goes back to the agent
   ```
   Edit them, push to GitHub. CI cherry-picks the accepted commits, drops the rejected ones
   (their comments reopen with your reason), tags a rollback point, and regenerates the redline
   with what is still pending. Pull in Overleaf. Real undo is git history, not the editor.
5. `review/CHANGELOG.md` is generated from the trailers: what changed, why, and where.

## Setup (researcher)

1. In Overleaf: Menu → GitHub, create the repository. (Overleaf's GitHub/Git sync is a
   premium feature; see [docs/design.md](docs/design.md#10-overleaf-compatibility-notes) for
   free-plan routes.)
2. On github.com add `.github/workflows/paper-review.yml` (the 10-line file `paper-review init`
   generates, or copy [the template](src/paper_review/templates/workflow.yml)).
   On its first run CI adds `.paper-review.yml`, `AGENTS.md`, `CLAUDE.md` and `review/`.
3. In Overleaf click *Pull from GitHub* once.
4. Give your agent the repository; it reads `AGENTS.md` / `CLAUDE.md`. It needs push access to
   create `agent/round-N` branches.

You never need to run the CLI yourself.

## CLI (agents, CI, offline use)

```
paper-review init [--mode suggest]   add config, workflow, agent instructions
paper-review build                   PDF + build/pages/*.png + build/text.json + synctex
paper-review sync                    markers -> comments
paper-review list|show|reply|resolve comment operations (all support --json)
paper-review round                   next agent/round-N name
paper-review redline <branch>        write review/redline.tex
paper-review apply                   apply accept/reject decisions
paper-review changelog               write review/CHANGELOG.md
paper-review ci [--push]             what the workflow runs
paper-review doctor                  check environment
```

Install: `pip install paper-review` (from a checkout: `pip install -e .`). It needs
`latexmk` and `latexdiff` (TeX Live) on the PATH, or use `docker/Dockerfile`, the same
toolchain as CI. Offline use is just `paper-review build` on a clone.

## What is verified

Tested here (`pytest`, 19 tests, real git and real TeX Live): marker parsing, comment
lifecycle, build outputs (PDF, page PNGs, text boxes), redline generation and that it
**compiles to a PDF**, change attribution to commits, accept / reject / pending, conflict
rollback, stale-redline refusal, asset handling, change log, and the CI entry points against a
real bare remote.

**Not verified**, so treat as unproven until tried on a scratch project:
- the reusable GitHub workflow on real Actions runners (image, Python install, permissions);
- Overleaf compiling `redline.tex` as a main document and syncing the generated files;
- whether Overleaf's GitHub sync follows only the default branch;
- agent behaviour with `AGENTS.md` across vendors.

## Known limits

- Overleaf's compiler and TeX Live version are project settings that are not in git; set
  `engine` in `.paper-review.yml` if you don't use pdfLaTeX (`doctor` warns).
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
