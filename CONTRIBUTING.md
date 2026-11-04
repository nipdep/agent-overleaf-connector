# Contributing

Thanks for helping. This project is small and the maintainer reads every issue and pull request.
Read [docs/usage.md](docs/usage.md) for what the tool does, [docs/design.md](docs/design.md) for the reasoning behind
decisions (it also records the earlier Python version), and [docs/status-and-roadmap.md](docs/status-and-roadmap.md)
for what is open.

## Ground rules

- **A connector, not a policy.** The tool gives agents capabilities and honours what the researcher chose (tags,
  decisions in Overleaf). Please do not add features that decide how an agent should work for a given kind of task;
  those belong in instructions (`src/agents-md.js`, the user's `AGENTS.md`).
- **Never handle secrets carelessly.** The session cookie lives only in `~/.config/olmcp/config.json` (mode
  0600) or `OVERLEAF_SESSION`. Never log, print or send it anywhere, and do not paste it into issues.
- **No way to resolve, reopen or delete a thread.** That is a deliberate property; do not add one.
- **No runtime dependencies** unless there is a strong reason; the package is plain Node 20+.
- **Tests come with the change.** Behaviour you add or change needs a test; so does every bug you fix.

## Development

CI runs the tests on Linux and macOS with Node 20 and 22. Windows is untested: `test/regression.test.js` assumes npm's
Unix layout (`<prefix>/bin/olmcp`), so a Windows job needs that test adapted first.

```bash
git clone https://github.com/nipdep/agent-overleaf-connector && cd agent-overleaf-connector
npm test                       # node --test, against a fake Overleaf; nothing needs the network
node src/cli.js help
```

`test/fake-overleaf.js` imitates the parts of Overleaf the client uses: the project page with the CSRF token, the
project socket over Socket.IO 0.9 long polling, joining documents, applying operations (tracked or not), thread
endpoints, compile and download. It encodes how the protocol is understood from olcli's source and from
Overleaf's behaviour, so it cannot prove the real service agrees.

## Making a change

1. Branch from `main` and open a pull request (the template lists what to include).
2. Write the test first or alongside the change.
3. Keep the docs true: `README.md`, `docs/usage.md`, `docs/agents.md`, `src/agents-md.js` (what agents are told),
   `docs/status-and-roadmap.md` (move things between "verified" and "not verified"), `CHANGELOG.md`.
4. Add a `CHANGELOG.md` entry and bump `version` in `package.json` (the only place). While the
   project is 0.x: a feature or behaviour change is a minor bump, a fix is a patch.
5. Conventions: ES modules, no shell strings for subprocesses, the `mcp` command must keep stdout clean (it is the
   protocol channel), and agent-facing refusals are `ToolError` messages that say how to retry.

## Testing against real Overleaf

Automated tests cannot reach the real Overleaf, so changes to `src/client.js`, `src/socketio.js`, `src/ranges.js`
or the thread messages need this check on a **scratch project** (never your real paper) before release:

1. `olmcp doctor --project <id>`: all `[ok]`.
2. A comment on selected text shows up in `olmcp list` with the right `selected_text`, including after a
   non-ASCII character earlier in the file.
3. `edit <id> main.tex --old "..." --new "..." --dry-run`, then without it: Overleaf shows a tracked deletion and
   insertion; Reject restores the text; Accept keeps the new text.
4. The same in a file inside a folder, and where another tracked change already exists (it must refuse).
5. `--direct`: the text changes with no tracking.
6. `olmcp pdf <id> -o /tmp/p.pdf` produces the PDF; a deliberate TeX error prints the error lines.
7. An agent with `olmcp mcp`: `#no-agent` comments are ignored, `#agent` focuses, the thread gets the reply
   with the diff and stays unresolved.

Record the result in `docs/status-and-roadmap.md`.

## Releasing

Versions: `1.0.0-alpha.N` while real-Overleaf bugs are still being found, `1.0.0-beta.N` when the alpha scenarios pass
on several projects and computers, then `1.0.0`. After 1.0.0: new features are minor (`1.1.0`), fixes are patches
(`1.0.1`), and anything that breaks the command, a tool's arguments or the tag syntax is a major release.

1. Everything merged; CI green on `main`.
2. `CHANGELOG.md` has the version; `package.json` has that version.
3. Tag and publish (users can then pin `npm install -g github:nipdep/agent-overleaf-connector#vX.Y.Z`):

   ```bash
   git tag -a vX.Y.Z -m "olmcp X.Y.Z"
   git push origin vX.Y.Z
   ```

## Reporting problems

Use the issue templates. For a bug include the version, your OS and Node version, which agent you use, the command
you ran and its output, and `olmcp doctor`. **Remove cookies, names and emails first.** For a security
problem, do not open a public issue: use the repository's Security tab (Report a vulnerability) or contact the
maintainer directly.
