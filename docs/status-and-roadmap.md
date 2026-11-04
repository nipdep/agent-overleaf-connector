# Status and roadmap

Version 0.3.x. Early: used by the author on a real project; not yet by anyone else. Update this page with every change
that moves something between columns.

## Verified

| Area | How |
|---|---|
| Reading comments (selected text, threads) on a real project | The author (`doctor`/`check` read 15 threads) |
| Replies appear in the thread | The author |
| `review` mode: tracked deletion and insertion with a thread reply, reject/accept in Overleaf | The author, on a real project |
| Use from Claude Code and Codex | The author (earlier with the Python version; the Node server was used with Codex) |
| MCP protocol | Tests, and the official Python MCP SDK's client against the server |
| Everything above except real Overleaf | 46 automated tests against a fake Overleaf (`npm test`), including a regression suite: the packed program installed into a clean prefix and run end to end, the cookie never appearing in output, no resolve/reopen/delete anywhere, a stable tool surface, docs commands that exist, a 24-document project |

## Not verified

| Area | Why it matters |
|---|---|
| `direct` mode and tags (`#no-agent`, `#agent`) on a real project | Tested against the fake only |
| `render_pdf` | Tested against the fake only |
| Documents in Overleaf's newer history format | Refused for editing; reading untested |
| Large projects | Every call joins every document |
| macOS (CI runs the tests there, never run by hand), Windows (not tested; the docs' `$(which olmcp)` is bash) | Nothing in the code is OS-specific, but only Linux has been used for real |
| Claude Code through this server; other MCP clients | |

## Known limits

- Tracked changes are attributed to your account; there is one Overleaf identity.
- No command resolves, reopens or deletes threads (by design).
- The cookie expires after a few days; the interface is unofficial.

## Open

| Question | Where it stands |
|---|---|
| Per-hunk decisions, `%% @agent:` markers, Git sync, `redline.tex` | Existed in the Python version (`python-legacy` branch); not ported, `review` mode covers the main use |
| ChatGPT chat support | Needs an HTTP mode, a tunnel and real authentication |
| Release tags and npm publishing | Not done; install from GitHub |
| Page images for agents that cannot read PDFs | Not built |
