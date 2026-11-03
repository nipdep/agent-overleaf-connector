# The Overleaf client (`olmcp-overleaf`)

A small Node program in `node/` that talks to Overleaf's web interface for what Git cannot carry: **comments** and
**tracked changes**. It is the only Overleaf client the tool uses (it replaced `olcli`), has no runtime dependencies, and needs Node 20 or later. Its Overleaf
protocol handling follows the approach in [olcli](https://github.com/aloth/olcli) by Alexander Loth (MIT); see
`node/THIRD_PARTY_NOTICES.md`.

**Status: reading comments and review-mode (tracked-change) edits are verified on a real project by the author.
`pdf` is tested against a fake Overleaf only.**

## Install and sign in

```bash
cd node && npm install -g .          # gives the command olmcp-overleaf
olmcp-overleaf auth --cookie "<value of the overleaf_session2 cookie>"
```

The cookie is stored in `~/.config/olmcp-overleaf/config.json` with mode 0600 (or give it in `OVERLEAF_SESSION`).
Use `--base-url` for a self-hosted Overleaf. `.olmcp.yml` needs nothing: the command name is the default of
`overleaf_client`.

## What it can and cannot do

| Command | Does |
|---|---|
| `comments list <project> [--status] [--json]` | Threads with selected text, file, line, and messages |
| `comments reply <thread> <text> <project>` | Post a message into a thread |
| `changes list <project>` | Pending tracked changes |
| `pdf <project> [-o FILE] [--draft]` | Compile with **Overleaf's own compiler** (your TeX Live version) and save the PDF; a failed compile prints the TeX error lines |
| `edit <project> <file> --old A --new B` | Make the edit as a **tracked change** (the researcher accepts or rejects it in Overleaf) |
| `edit ... --direct` | Make it as a plain edit |
| `edit ... --dry-run`, `--stdin` | Show the operations; read many edits as JSON |

It has **no command to resolve, reopen or delete a thread**, on purpose. That removes the capability an agent
could reach through this program. It does not remove the session cookie: anything that can read
`~/.config/olmcp-overleaf/config.json` can still call Overleaf as you.

## Tracked-change edits

`edit` joins the document over Overleaf's live-editing socket and sends operations marked with a tracking id, the
way the editor does in Reviewing mode. Each edit becomes a tracked deletion of the old text plus a tracked insertion
of the new text. It refuses an edit if the old text is missing or appears twice, or if it overlaps an existing
tracked change, and afterwards re-reads the document and fails loudly if Overleaf did not record the edit as
tracked (so a plain edit never passes silently as a suggestion).

Limits: the change is attributed to **your** Overleaf account (the agent uses your cookie); documents in Overleaf's
newer history format are refused for now; whether Overleaf's Git export includes pending tracked changes, and how
they interact with `olmcp pull`, is not yet established. Overleaf itself warns against mixing Git pushes with
tracked changes.

## Using it from the agent: `review` mode

With `mode: review` in `.olmcp.yml` (or `#review` in a comment) the agent's `address_comment` sends its edits through
`edit`, so they appear in Overleaf as tracked changes, and the thread reply says so. Git is not touched.

## Scratch-project checklist (before real use)

1. `olmcp-overleaf check <project>` prints `ok: N comment thread(s) readable`.
2. `comments list <project> --json` shows your comment with the right `selectedText` and `path`, including after a
   non-ASCII character earlier in the file.
3. `comments reply ...` appears in the thread in Overleaf.
4. `edit <project> main.tex --old "..." --new "..." --dry-run`, then without `--dry-run`: Overleaf shows a tracked
   deletion and insertion, attributed to you; Reject restores the original; Accept keeps the new text.
5. Do the same in a second file inside a folder, and on a document that already contains another tracked change.
6. Edit once more with `--direct`: the text changes with no tracking.
7. Report back what differed. The parts most likely to differ from the fake: the tracking id format
   (`meta.tc`), the socket acknowledgement format, and `/project/<id>/threads` message fields.
