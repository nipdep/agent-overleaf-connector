# paper-review: design

> **Implementation status (v0.1).** This document is the design; the code in `src/` implements
> the parts listed under "Built" and deviates in the ways listed under "Changed since the first
> draft". Everything else is future work.
>
> **Built:** reproducible build and page images; marker comments (`%% @agent:`) and the comment
> store; CLI for agents; `direct` and `suggest` modes; latexdiff `review/redline.tex` with
> in-file `decision[...]` lines; `apply` (cherry-pick accepted, drop rejected, reopen with reason,
> rollback tag, conflict rollback); change log from `Resolves:` trailers; `init`; reusable GitHub
> workflow and Dockerfile.
>
> **Changed since the first draft** (decisions made while designing with the user):
> - Overleaf is the primary surface. Comments are marker lines in the source (no tooling);
>   native Overleaf comments are an optional adapter, not implemented.
> - The redline is delivered as `review/redline.tex`, usable as an Overleaf main document, with
>   accept/reject typed in the file and applied by CI. `suggest` mode pushes a branch, no PR.
> - Comments live in `review/comments/`, not a root `reviews/` folder (the repo layout is dictated
>   by Overleaf, so the tool owns only `review/`, `.paper-review.yml`, the workflow file and
>   `AGENTS.md`/`CLAUDE.md`).
> - The viewer/server is deferred; offline use is `paper-review build` on a clone.
> - Python implementation, Apache-2.0 license.
>
> **Not built:** local viewer/server, PDF-annotation and Overleaf comment adapters, WASM build,
> SyncTeX-based click-to-source, automatic `stale` marking, per-hunk decisions.

An open-source, GitHub-native toolkit for the review-and-revise loop on LaTeX papers
when the editor is Overleaf, the agent is an LLM, and neither can see the other's
view of the paper.

Status: design draft. Nothing is built. Claims about third-party tools are from
READMEs and are unverified.

---

## 1. Problem

Papers are written in Overleaf and reachable by agents only through Overleaf's Git or
GitHub sync. That leaves three gaps:

1. **No eyes.** The agent cannot see the rendered PDF or figures.
2. **No comments.** Overleaf review comments live in Overleaf's database, not in git,
   and Overleaf has no public API for them. There is no way to say "improve this
   paragraph" and have an agent pick it up.
3. **No audit trail.** It is hard to see what changed, why, and in response to what.

## 2. Goals and non-goals

Goals
- G1. Reproducible build of the PDF, page images and source map, identical on CI,
  on a laptop and in an agent's container.
- G2. A comment model the human and the agent both read and write, stored in git.
- G3. Two edit modes: `direct` and `suggest` (redline for review).
- G4. A change log tying every change to the comment that caused it.
- G5. Works offline once cloned. No required hosted service.
- G6. Agent-agnostic. No dependency on any one vendor's MCP or plugin system.
- G7. Easy to adopt: GitHub template repo, or one reusable action added to an
  existing repo.

Non-goals
- Replacing Overleaf as an editor.
- Real-time co-editing.
- Depending on any unofficial Overleaf API in the core.
- Full LaTeX rendering in pure JavaScript (not feasible for real papers).

## 3. Principles

1. **Git is the database.** Comments, resolutions and logs are plain files.
2. **One build pipeline.** Everything that renders uses the same container recipe.
3. **The CLI is the agent interface.** Any agent that can run a shell command can use
   the system. An MCP wrapper can be added later but is never required.
4. **Anchor to text, not to offsets.** Comments survive edits and re-builds.
5. **Core stays clean; Overleaf is a plugin.** Unofficial integrations live outside it.

## 4. Architecture

```
            ┌───────────────────────── GitHub repo (source of truth) ─────────────────────────┐
 Overleaf ⇄ │ *.tex  figures/  reviews/*.json  .paper-agent.yml  AGENTS.md  CHANGELOG.md       │
 (sync)     └───────┬───────────────────────────────┬────────────────────────────┬────────────┘
                    │                               │                            │
             ┌──────▼──────┐                ┌───────▼────────┐           ┌───────▼────────┐
             │ build       │                │ paper-review   │           │ GitHub Actions │
             │ (container) │◄───────────────│ CLI + server   │           │ (reusable)     │
             └──────┬──────┘                └───────┬────────┘           └───────┬────────┘
   pdf, pages/*.png, synctex, text.json            │                            │
             ┌──────▼──────┐   comments     ┌──────▼──────┐             redline PDF, changelog,
             │ viewer      │───────────────►│ reviews/    │             Pages site, PR comment
             │ (PDF.js)    │                │  C-NNNN.json│
             └─────────────┘                └──────▲──────┘
                                                   │ read / resolve
                                            ┌──────┴──────┐
                                            │ agent       │
                                            └─────────────┘
```

Components
- **Build** (`make pdf`): pinned TeX Live container; runs latexmk with SyncTeX.
- **CLI** (`paper-review`): the single entry point for humans, CI and agents.
- **Viewer + local server**: browser UI for reading and commenting.
- **Actions**: build, diff, changelog, publish, as a reusable composite action.
- **Adapters** (optional): import comments from other sources, for example Overleaf.

## 5. Repository layout (template)

```
paper/                      LaTeX source (main.tex, sections/, figures/, refs.bib)
reviews/                    one JSON file per comment: C-0001.json, ...
reviews/_meta.json          id counter, schema version
build/                      generated, gitignored (pdf, pages, text.json, synctex)
.paper-agent.yml            config (mode, main file, engine, image tag)
AGENTS.md                   agent protocol (see 9)
CHANGELOG.md                generated
.devcontainer/              same image as CI
.github/workflows/          uses: nipdep/agent-overleaf-connector/.github/workflows/review.yml@main
Makefile                    pdf, pages, serve, diff, changelog
```

## 6. Build outputs

`make pdf` produces, under `build/`:

| File | Purpose |
|---|---|
| `paper.pdf` | The rendered paper. |
| `paper.synctex.gz` | Page/position ⇄ source line mapping. |
| `pages/p-001.png` ... | What the agent looks at. Resolution configurable. |
| `text.json` | Per-page text with word bounding boxes. Used to anchor and re-anchor comments. |
| `build.json` | Commit hash, engine, image digest, timestamp, warnings. |

Reproducibility: the container image is pinned by tag and digest in config. The same
image is used by CI, the devcontainer and the agent environment.

## 7. Comment model

One file per comment so concurrent additions never conflict in git.

```json
{
  "schema": 1,
  "id": "C-0042",
  "kind": "comment",
  "status": "open",
  "created": "2026-11-02T10:12:00Z",
  "author": "human:nipun",
  "body": "Claim is too strong; soften and cite.",
  "anchor": {
    "build_commit": "ab12cd3",
    "page": 3,
    "quote": "our method always outperforms",
    "prefix": "On all benchmarks ",
    "suffix": " the baselines",
    "source": { "file": "paper/sections/results.tex", "line": 88, "confidence": 0.94 }
  },
  "thread": [ { "author": "agent:claude", "at": "...", "body": "Proposed: ..." } ],
  "resolution": { "commit": "ef45a67", "by": "agent:claude", "note": "Softened, added cite." },
  "origin": { "type": "viewer", "external_id": null }
}
```

- `kind`: `comment`, `question`, `change-request`, `note`.
- `status`: `open` → `addressed` (agent changed it) → `resolved` (human accepted) or
  `wontfix`. `stale` is set when the quote can no longer be found.
- **Anchor** follows the quote + prefix + suffix selector idea from W3C Web
  Annotation, so it is portable and standards-based.
- **Re-anchoring.** On each build, every open comment is searched in `text.json`
  (fuzzy match, prefix/suffix as disambiguators) and in the .tex source (SyncTeX gives
  a line hint; the quote is the truth). Confidence below a threshold marks the
  comment `stale` for human attention instead of silently moving it.
- `origin` records where a comment came from, enabling de-duplication across adapters.

## 8. Components in detail

### 8.1 CLI (agent- and human-facing)

```
paper-review build                       # pdf + pages + text.json + synctex
paper-review serve [--port]              # local viewer + API
paper-review list [--status open] [--json]
paper-review show C-0042 [--context N]   # quote, tex snippet, page image path, thread
paper-review reply C-0042 "..."
paper-review resolve C-0042 --commit HEAD
paper-review diff [BASE] [HEAD]          # latexdiff redline PDF
paper-review changelog                   # regenerate CHANGELOG.md
paper-review import <adapter>            # optional adapters
paper-review doctor                      # environment and config check
```

All commands support `--json` so agents parse output reliably. No command pushes to
git; committing stays with the user or the agent's own workflow.

### 8.2 Viewer and local server

- PDF.js viewer; select text to add a comment; sidebar lists threads by status.
- Selecting text produces quote/prefix/suffix and page; the server fills `source`
  from SyncTeX and re-anchoring.
- Double-click on text opens the source location (editor URL scheme, configurable).
- Live reload: file watcher → rebuild → viewer refresh; comments re-anchor after each
  build.
- Writes only `reviews/*.json` in the working tree. Binds to localhost.
- A static read-only build of the viewer can be published to GitHub Pages for reading
  and for reviewers without a local setup.

### 8.3 Edit modes (`.paper-agent.yml: mode`)

| | `direct` | `suggest` |
|---|---|---|
| Where edits land | current branch | `agent/round-N` branch (push only) |
| Commit granularity | one per comment | one per comment (required) |
| Human review | read the diff after | review redline PDF before merge |
| Accept | already applied | merge the branch |
| Reject one item | revert the commit | revert or drop that commit |
| Commit trailer | `Resolves: C-0042` | `Resolves: C-0042` |

Redline: `latexdiff` between base and head, built by CI into `redline.pdf`, with a
table of changes keyed by comment id. An opt-in `inline` variant wraps edits with the
`changes` package so the redline shows in any normal build, at the cost of cluttering
the source.

### 8.4 Change log

Generated from commit trailers and review files, not hand-written:

```
## Round 3
- C-0042 (results.tex:88) "Claim too strong": softened wording, added cite. [ef45a67]
- C-0047 (fig 4) "Axis labels unreadable": regenerated at 8pt. [91b2c0d]
```

Gives what changed, why (the comment), and where (commit).

### 8.5 Agent protocol (`AGENTS.md`)

The template ships instructions any agent can follow:

1. `paper-review build` and look at the page images around each comment.
2. `paper-review list --status open --json`.
3. For each comment: `show`, edit the .tex, rebuild, check the render, commit with
   `Resolves: C-NNNN`, then `resolve`. Reply instead when a question needs the human.
4. Obey `mode`. In `suggest`, never touch the default branch.
5. Never delete or rewrite a human comment. Mark ambiguous ones with a reply.

### 8.6 Adapters (optional, outside core)

Contract: an adapter reads an external source and writes valid `reviews/*.json` with
`origin` set. It may support write-back (reply, resolve) when the source allows it.

Planned: `pdf-annotations` (read highlights and notes saved by any PDF viewer, via
PyMuPDF); `overleaf` (wraps a community tool such as olcli or netique/overleaf-mcp,
unofficial and fragile).

Overleaf adapter rules: runs on the user's machine; credentials never enter the repo
or the agent's environment; imports are idempotent via `origin.external_id`; comment
text is matched by quote, because Overleaf offsets refer to Overleaf's state, which may
differ from GitHub's.

## 9. GitHub integration

- **Template repo** for new papers. **Reusable composite action** for existing ones.
- Workflow on push (and PR, if one is opened): build → upload artifacts (PDF, pages)
  → on `agent/*` branches produce the redline artifact → on the default branch,
  regenerate the changelog and publish the viewer to Pages.
- Comments are files, so they appear in normal PR diffs and history.
- A GitHub Issues mirror is possible later; it needs network and auth, so it is never
  the primary store.

## 10. Overleaf compatibility notes

- Overleaf's GitHub sync is manual in both directions (push/pull buttons).
- Overleaf's docs warn that pulls from GitHub can lose or displace Overleaf's own
  comments and tracked changes. This project avoids relying on them for that reason.
- As far as I know, sync follows only the default branch, so `suggest` mode is
  reviewed via the CI redline, then merged, then pulled in Overleaf. Verify.
- Work in rounds to avoid conflicts: comment → agent edits → merge → pull in Overleaf.

## 11. Security and privacy

- Unpublished research is sensitive. The viewer binds to localhost; Pages publishing
  is opt-in and warns on private repos.
- No secrets in the repo. Adapter credentials are read from the local environment.
- The agent's CLI is the only write path to `reviews/`; schema-validate on every read.
- Treat comment text as data, not instructions, when handed to an agent. The agent
  protocol states this, so a pasted or imported comment cannot redirect the agent.

## 12. Failure modes

| Failure | Handling |
|---|---|
| Quote not found after edits | status `stale`, listed by `doctor`, never auto-moved |
| PDF out of date vs comment | `build_commit` recorded; viewer warns on mismatch |
| Build fails | `build.json` holds the log tail; agent must fix before resolving |
| Duplicate import | idempotent on `origin.external_id` |
| Agent edits default branch in `suggest` | CI check fails when a `Resolves:` commit lands outside an `agent/*` branch |
| Overleaf API change | only the adapter breaks; core unaffected |

## 13. Technology choices (proposed)

- CLI and anchoring: **Python** (PyMuPDF for text boxes, easy to pipx-install).
- Viewer: static **PDF.js** page, minimal dependencies, no framework.
- Server: small local HTTP server, same package as the CLI.
- Build: **latexmk** in a pinned TeX Live image; **latexdiff** for redlines.
- Config: YAML; comment files: JSON with a versioned schema.

## 14. Milestones

1. **M1 Build:** template, Makefile, container, CI building PDF, PNGs, SyncTeX, text.json.
2. **M2 Comments:** schema, anchoring and re-anchoring, CLI `list/show/reply/resolve`.
3. **M3 Viewer:** local server, text selection to comment, live reload, click to source.
4. **M4 Modes:** agent protocol, `suggest` flow, latexdiff redline, sticky PR comment,
   changelog.
5. **M5 Adapters:** PDF annotations, then an Overleaf spike.
6. **M6 Polish:** docs, example paper, Pages viewer, release as template and action.

## 15. Decisions

- **License:** Apache-2.0.
- **Implementation language:** Python (PyMuPDF for text boxes). This is an
  implementation detail: file formats and the CLI interface are language-neutral.
  Anchoring runs only in the server; the viewer sends the selected text and page and
  holds no matching logic, so no logic is duplicated between languages.
- **`suggest` mode:** pushes a branch `agent/round-N`. It does not open a PR. CI still
  builds the redline for pushes to `agent/*` branches and publishes it as an artifact
  (and a Pages preview if enabled); the sticky PR comment is used only if the user
  opens a PR themselves.

## 16. Open questions

1. Project name.
2. Is a WASM in-browser build tier worth supporting later? Needs a spike.
3. Which Overleaf adapter is dependable enough today? Needs a spike on a scratch
   project.
4. Multi-file and multi-document papers (appendix, supplementary): anchor `source.file`
   is already per file; the viewer needs a document switcher.
5. Figures made outside LaTeX (matplotlib scripts): include a `figures` build target and
   let comments anchor to a figure by label as well as by text.
