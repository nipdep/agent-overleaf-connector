# Changelog (the tool, not your paper's change log)

Bump `version` in `pyproject.toml` for every change that users can notice, and add a line here.

## 0.2.0
- Local mode: `paper-review pull` / `push` around an agent task (Overleaf Git remote, no CI, no polling).
- `init --local`; `remote` / `remote_branch` config.
- **The redline moved:** `redline.tex` now sits beside the main file instead of `review/redline.tex`
  (so Overleaf resolves its paths like the paper's). A leftover `review/redline.tex` is removed on
  the next `push`, with typed decisions carried over.
- The generated redline is never chosen as the main file nor scanned for markers.
- Pushes the pre-apply rollback tag in CI mode; real unresolved-reference count in `build.json`.
- Design v2 document (diff-based review, replies, dependency tree; mostly planned).

## 0.1.0
- First version: build, marker comments, `direct` / `suggest` modes, flattened latexdiff redline,
  accept/reject via `apply`, change log, reusable GitHub workflow.
