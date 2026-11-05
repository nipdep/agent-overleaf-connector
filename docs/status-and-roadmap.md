# Status and roadmap

The project is at version 1.0.0-alpha.3 and is still early. The author uses it on a real project, but it has not yet been tested by a wider group of users.

This page separates what has been verified from what still needs real-world testing. It also records current limitations and the next planned work. Update it with every change that moves something between columns.

## Verified

| Area | How |
|---|---|
| Reading comments (selected text, threads) on a real project | The author (`doctor`/`check` read 15 threads) |
| Replies appear in the thread | The author |
| `review` mode: tracked deletion and insertion with a thread reply, reject/accept in Overleaf | The author, on a real project |
| Use from Claude Code and Codex | The author (earlier with the Python version; the Node server was used with Codex) |
| MCP protocol | Tests, and the official Python MCP SDK's client against the server |
| Everything above except real Overleaf | 57 automated tests against a fake Overleaf (`npm test`), including pending-suggestion revision, safe file creation, and a regression suite: the packed program installed into a clean prefix and run end to end, the cookie never appearing in output, no resolve/reopen/delete anywhere, a stable tool surface, docs commands that exist, a 24-document project |

## Not verified

| Area | Why it matters |
|---|---|
| Creating new files (`create_file`) | Uses the editor's upload endpoint like olcli; fake only so far (alpha test plan scenario 12) |
| Revising a pending suggestion in place (`address_comment` on suggested text) | Depends on how Overleaf's ranges tracker treats a delete/insert inside your own tracked insertion; the fake models it, the real service is untried (alpha test plan scenario 11) |
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
