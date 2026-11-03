# Using it

## The loop

```
you comment in Overleaf  →  tell the agent "address the review comments"  →  you accept or reject in Overleaf
```

The agent lists your open comments, and for each one makes the edit and replies in the thread. There is nothing to
pull or push: the tool works on the live project, so your edits and the agent's are in the same document.

## Making a comment

Select text in Overleaf's editor and add a Review comment. The agent receives your message, the selected text, the
file and line, and the whole thread. A later message you write in the thread is a follow-up it will see; if the
agent had already answered, the comment is open again.

A comment's status is derived from its thread: **open** (needs the agent), **addressed** (the agent's reply is the
last message), **resolved** (you closed it).

## Review or direct

- **`review`** (default): the edit is written into Overleaf as a **tracked change**: a tracked deletion of the old
  text and a tracked insertion of the new, which you accept or reject in the Review panel. Reject restores your text.
- **`direct`**: the edit is applied as a plain edit (undo it with Overleaf's History).

Default: `mode` in `.olmcp.json` (or `OLMCP_MODE`); `olmcp init <id> --mode direct` sets it.
Per comment, use a tag. The agent may choose a mode only for untagged comments.

## Comment tags (all optional)

Write hashtags anywhere in a comment, for example `we need to fix the wording here to shorten this #agent #suggest`.

| Tag | Effect |
|---|---|
| `#agent` | Focus: while any open comment has it, only those are listed for the agent |
| `#no-agent` | Hands off: the comment is hidden from the agent and its tools refuse to edit or reply to it |
| `#review` / `#suggest` | Make the edit as a tracked change |
| `#direct` | Make the edit as a plain edit |

If tags conflict in one comment the safe side wins: `#no-agent` beats `#agent`, and `#suggest`/`#review` beats
`#direct`. The latest message of yours that carries a tag decides. Focus is advisory (the agent can be told to
do all comments); `#no-agent` is enforced. Tags are removed from the request text the agent reads. Without tags
everything works as usual; `.olmcp.json` with `"commentTags": false` turns tag reading off.

## What the agent's reply shows

```
[agent] Softened the claim.

Tracked change in sections/results.tex:
Our method [-always-] outperforms [-the-]{+most+} baselines
(Made as a tracked change in this document: accept or reject it in the editor's Review panel; ...)
```

`[-removed-]{+added+}` is an inline word diff. The agent never resolves a thread: **a handled comment stays open
until you resolve it**.

## The tools (MCP) and the CLI

| Tool | CLI | Does |
|---|---|---|
| `list_comments` | `list [--status s] [--all]` | Comments with selected text, request, thread, mode, `for_agent` |
| `show_comment` | `show ID` | One comment with its thread |
| `list_files`, `read_file` | | The project's text documents |
| `address_comment` | `address ID < edit.json` | Edits plus the reply, together; validated first |
| `reply_to_comment` | `comments reply THREAD TEXT PROJECT` | Reply without editing |
| `list_tracked_changes` | `changes list PROJECT` | Pending tracked changes |
| `render_pdf` | `pdf PROJECT -o file.pdf` | Compile with Overleaf's compiler, save the PDF |

Other commands: `auth`, `init`, `doctor`, `check PROJECT`, `edit PROJECT FILE --old A --new B [--direct] [--dry-run]`,
`comments list PROJECT [--json]`. Run `olmcp help`. There is no command to resolve, reopen or delete a
thread, on purpose.

## What `address_comment` enforces

- Every edit's `old` text must occur exactly once in the live document and must not overlap an existing tracked
  change; otherwise nothing is written and the error says why.
- Several files: all are validated before any is written. The reply is posted only after the edits are in.
- A `#no-agent` comment is refused; a tag that disagrees with the agent's `mode` argument is refused.
- Text that carries a pending tracked deletion is still present in what `read_file` returns.

## Limits

- Tracked changes are attributed to **your** Overleaf account (the tool acts with your cookie).
- Documents in Overleaf's newer history format are read but not edited yet.
- Unofficial interface: it can break when Overleaf changes, and the cookie expires after a few days.
- Overleaf's own warning applies: pushing from Git while tracked changes are pending can displace them. This tool
  does not use Git.
