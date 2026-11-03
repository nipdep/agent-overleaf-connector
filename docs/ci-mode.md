# CI mode: the GitHub-sync alternative

The recommended setup is [local mode](setup.md): a clone of your Overleaf project's Git remote, with `olmcp
pull` / `push` around the agent's work. **CI mode** is for when nothing should run on your machine: Overleaf's
GitHub sync connects the project to a GitHub repository, and a GitHub Actions workflow does the work.

Trade-offs: each round costs two manual clicks in Overleaf (Push to GitHub, Pull from GitHub) and a 2 to 3
minute workflow run, and it needs the GitHub sync (also a premium Overleaf feature). Native Overleaf comments
are not available in this mode (they need `olmcp-overleaf` and a local clone); `%% @agent:` markers are.

## Setup

1. In Overleaf: Menu, GitHub, create the repository.
2. Add `.github/workflows/olmcp.yml` to the repository (on github.com, or let `olmcp init` write it):

   ```yaml
   name: olmcp
   on:
     push:
       branches: ["main", "agent/**"]
   permissions:
     contents: write
   jobs:
     review:
       uses: nipdep/agent-overleaf-connector/.github/workflows/review.yml@main
       with:
         texlive_image: texlive/texlive:TL2025-historic   # match Overleaf, see below
   ```

   On its first run the workflow adds `.olmcp.yml`, `AGENTS.md`, `CLAUDE.md` and `review/`.
3. In Overleaf click Pull GitHub changes once.
4. Give your agent the repository. It needs push access to create `agent/round-N` branches.

## What the workflow does

- Push to the default branch: builds the PDF and page images (uploaded as an artifact), turns `%% @agent:`
  markers into comments, applies accept/reject lines typed in `redline.tex`, refreshes the change log.
- Push to `agent/**`: regenerates `redline.tex` on the default branch.
- Bot commits carry `[skip ci]`, so they do not re-trigger the workflow.

## Match Overleaf's TeX Live version

Overleaf's compiler and TeX Live version are project settings that are **not stored in git**, and they matter.
On the TGDK journal class, `texlive/texlive:latest` failed with `Command \c@lemma already defined` while
`texlive/texlive:TL2025-historic` built it. Set `texlive_image` to the version in Overleaf (Menu, Settings,
TeX Live version) and set `engine` in `.olmcp.yml` if you do not use pdfLaTeX.

## Limits

- The reusable workflow installs the tool from the `main` branch by default (`package` input); pin a tag or
  commit once releases are tagged.
- Private repositories use Actions minutes; the TeX Live image is large.
- Untested: branch protection on the default branch (the bot must be allowed to push), and whether Overleaf's
  GitHub sync follows only the default branch.
- Verified on real GitHub Actions on a demo paper and a real 31-page paper: the full round, mixed
  accept/reject, bot commits not re-triggering, and the rollback tag being pushed.
