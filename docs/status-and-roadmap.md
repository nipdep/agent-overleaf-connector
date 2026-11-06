# Status and roadmap

`olmcp` is currently **1.0.0-alpha.3**. It is usable, but it depends on Overleaf's unofficial web interface and still needs testing across more projects, accounts, and computers.

Use the [alpha test plan](alpha-test-plan.md) on a disposable project before trusting it with important work.

## At a glance

| Area | Status |
|---|---|
| Read Overleaf comments, selected text, and threads | Verified by the author on a real project |
| Reply in the original thread | Verified by the author |
| Propose review-mode tracked changes and accept/reject them in Overleaf | Verified by the author |
| Use through Codex | Verified by the author |
| Use through Claude Code with the current Node server | Needs broader real-project testing |
| Revise a pending tracked suggestion in place | Automated fake-Overleaf tests only |
| Create new files and folders | Automated fake-Overleaf tests only |
| Direct edits and comment tags | Automated fake-Overleaf tests only |
| Compile and download the PDF | Automated fake-Overleaf tests only |

## Automated coverage

The test suite covers the MCP protocol and tool surface, comments, tags, tracked and direct edits, pending-suggestion revision, safe file creation, PDF compilation, secret redaction, installation from a packed package, and a 24-document project. CI runs on Linux and macOS.

The fake Overleaf server cannot prove that undocumented production behavior has not changed. Real-service checks remain important.

## Known limits

- The connector uses a browser session cookie and an unofficial Overleaf interface. Either can stop working after an Overleaf change.
- The cookie expires periodically and represents your full Overleaf account.
- Tracked changes use your Overleaf identity; there is no separate agent identity.
- Documents using Overleaf's newer history format are not edited.
- Every operation currently inspects every document, so large projects may be slower.
- New files appear immediately because Overleaf cannot track file creation.
- There is intentionally no command to accept or reject changes, resolve or delete threads, or overwrite or delete files.
- Linux is used for real-project testing. macOS is covered by CI; Windows remains untested.
- ChatGPT chat apps cannot start this local stdio MCP server.

## Planned or open work

| Item | State |
|---|---|
| Verify pending-suggestion revision and new-file creation on real Overleaf | Next alpha testing priority |
| Test the current Node server through Claude Code and more MCP clients | Open |
| Support documents using the newer history format | Open; requires a different edit operation format |
| Improve performance for large projects | Open; avoid joining every document on every call |
| Produce page images for agents that cannot read PDFs | Planned |
| Publish release tags and an npm package | Not done; installation currently uses GitHub |
| Support remote ChatGPT-style MCP clients | Open; requires an authenticated HTTPS service |
| Restore Git sync, `%% @agent:` markers, `redline.tex`, or per-hunk decisions | Available only in `python-legacy`; port on demand |

Implementation details and design tradeoffs are documented in [Technical design](design.md). Release changes are recorded in the [changelog](../CHANGELOG.md).
