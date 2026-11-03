# Contributing

Thanks for helping. This project is small and the maintainer reads every issue and pull request.
For how the code is organised, read [docs/architecture.md](docs/architecture.md) first; for the reasoning behind
decisions, [docs/design.md](docs/design.md); for what is open, [docs/status-and-roadmap.md](docs/status-and-roadmap.md).

## Ground rules

- **A connector, not a policy.** The tool gives agents capabilities and honours what the researcher chose. Please do
  not add features that decide how an agent should work for a given kind of task; those belong in instructions
  (`templates/AGENTS.md`) the user can edit.
- **Never handle secrets.** Credentials stay with git and `olmcp-overleaf`. Do not log, store or print tokens or cookies, and
  do not paste them into issues.
- **Optional things stay optional.** Missing TeX, `olmcp-overleaf` or `latexdiff` must switch a feature off with a clear
  message, never break the core.
- **Tests come with the change.** Behaviour you add or change needs a test; so does every bug you fix.

## Development setup

```bash
git clone https://github.com/nipdep/agent-overleaf-connector && cd agent-overleaf-connector
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Needs Python 3.10+ and git. The suite uses real git. Tests that need `latexdiff` or `latexmk` are **skipped** when
those are missing, so install them to run everything:

```bash
sudo apt install -y latexmk latexdiff texlive-latex-base texlive-latex-recommended \
  texlive-fonts-recommended texlive-plain-generic       # macOS: brew install latexdiff, and a TeX distribution
```

Run part of it: `pytest tests/test_modes.py -q`, or `pytest -k redline`. Nothing in the suite needs the network
or a real Overleaf; native comments are tested against `tests/fake_overleaf_client.py`.

## Making a change

1. Branch from `main` and open a pull request (the template lists what to include).
2. Write the test first or alongside the change.
3. Keep the docs true. A user-visible change usually touches several of:
   - `README.md` and `docs/usage.md` (how it is used), `docs/agents.md` and `src/olmcp/templates/AGENTS.md`
     (what agents are told and what the tools enforce),
   - `docs/design.md` (a numbered section and the status table at its top), `docs/status-and-roadmap.md`
     (move things between "verified" and "not verified"),
   - `CHANGELOG.md`.
4. Add a `CHANGELOG.md` entry under a new version heading and bump `version` in `pyproject.toml` (the single
   source; `olmcp --version` reads it). While the project is 0.x: a new feature or a behaviour change is a minor
   bump (`0.9.0`), a fix is a patch (`0.9.1`). A change nobody can notice needs neither.
5. Conventions:
   - Python 3.10+, `pathlib`, `from __future__ import annotations`; no shell strings for subprocesses.
   - `mcp_server.py` must not use `from __future__ import annotations` (the SDK reads real annotations).
   - Library code never prints; only `cli.py` does, and the `mcp` command must keep stdout clean (it is the
     protocol channel).
   - Agent-facing refusals raise `ToolError` with a message that says how to retry.
   - Commit messages: a short imperative subject, then why.

## Testing against real Overleaf

Automated tests cannot reach the real Overleaf or the real Overleaf client, so changes that touch `overleaf.py`,
`local.py` or the thread messages need this check on a **scratch project** (never your real paper) before release:

1. `olmcp overleaf-check` prints `ok: project ...`.
2. Select text, comment in Overleaf; `olmcp pull` lists it with `on: "<selected text>"`.
3. Direct mode: the agent addresses it; the file changes in Overleaf; the thread gets an `[agent]` reply with
   `Edit applied` and the diff; the thread is **not** resolved.
4. A comment starting `[suggest]`: the reply says `Proposed edit`; `redline.tex` opened as the main document
   compiles and shows the change; resolving the thread then `olmcp pull` applies it; replying instead rejects it.
5. A follow-up reply reopens a handled comment; deleting a thread marks the comment `wontfix` on the next pull.
6. `olmcp mode suggest` / `direct` switches the default and `olmcp push` publishes the config line.
7. Overleaf's History shows the agent's pushes.

For the Node client (`node/`, `olmcp-overleaf`) the checklist is in [docs/overleaf-client.md](docs/overleaf-client.md);
`cd node && npm test` runs its tests against a fake Overleaf.

Record the result in `docs/status-and-roadmap.md`.

## Releasing

1. Everything merged; CI green on `main`.
2. `CHANGELOG.md` has the version heading with the date; `pyproject.toml` has that version; docs updated.
3. Tag and publish:

   ```bash
   git tag -a vX.Y.Z -m "olmcp X.Y.Z"
   git push origin vX.Y.Z
   ```

   Then create a GitHub release for the tag and paste the changelog entry into it.
4. Users can then pin: `pipx install "agent-overleaf-connector[mcp] @ git+https://github.com/nipdep/agent-overleaf-connector@vX.Y.Z"`,
   and the CI-mode workflow's `package` input can pin the same way.

## Reporting problems

Use the issue templates. For a bug include `olmcp --version`, your OS, which agent you use, your mode, the command
you ran and its output, and `olmcp doctor`. **Remove tokens, cookies, names and emails first.** For a security
problem, do not open a public issue: use the repository's Security tab (Report a vulnerability) or contact the
maintainer directly.
