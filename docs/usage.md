# Use `olmcp`

Most of the time, your workflow is simple:

```
you comment in Overleaf  →  tell the agent "address the review comments"  →  you accept or reject in Overleaf
```

The agent lists your open comments, and for each one makes the edit and replies in the thread. There is nothing to
pull or push: the tool works on the live project, so your edits and the agent's are in the same document.

## Ask for a change

Select text in Overleaf's editor and add a Review comment. The agent receives your message, the selected text, the
file and line, and the whole thread. A later message you write in the thread is a follow-up it will see; if the
agent had already answered, the comment is open again.

A comment's status is derived from its thread: **open** (needs the agent), **addressed** (the agent's reply is the
last message), **resolved** (you closed it).

## Choose how edits are applied

- **`review`** (default): the edit is written into Overleaf as a **tracked change**: a tracked deletion of the old
  text and a tracked insertion of the new, which you accept or reject in the Review panel. Reject restores your text.
- **`direct`**: the edit is applied as a plain edit (undo it with Overleaf's History).

Which project: the agent passes `project` (id, project URL or git URL) with each tool call, or it comes from `.olmcp.json`
(`olmcp init`), `--project`, `OVERLEAF_PROJECT` or the git remote of the folder.

Default: `mode` in `.olmcp.json` (or `OLMCP_MODE`); `olmcp init <id> --mode direct` sets it.
Per comment, use a tag. The agent may choose a mode only for untagged comments.

## Ask for another version, without accepting or rejecting

If you do not like a suggestion, you do not have to reject it before asking again. Reply in the thread ("shorter
please", "keep the citation"). The thread becomes open again and the agent **revises the suggestion in place**: the
suggested (new) text changes, the original text stays as the one pending deletion, and you still accept or reject a
single change at the end. Repeat as often as you like.

How it works: the agent reads the text as Overleaf stores it (suggested text in, deleted text out) and sends an edit
whose old text is the suggested text. `show_comment` lists the pending changes near the comment so the agent knows. This
only works on a suggestion made by your own account (that is the account the tool acts with); an insertion by a
collaborator is never rewritten, and a `#direct` edit never touches pending suggestions. After writing, the tool
re-reads the document and reports an error if Overleaf left the first suggestion behind as a struck-through deletion
(then reject that stray change in the Review panel).

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

In `review` mode the reply is just the agent's words, one to three plain sentences about what it did and why, because
Overleaf already shows the change itself (struck-through old text, added new text, Accept and Reject buttons):

```
[agent] Shortened the sentence and dropped the repeated claim.
```

A `direct` edit leaves no visible trace, so its reply adds **Before / After** of the changed passage (cropped to the
changed words plus a little context; `…` marks the crop) and a note that it was applied directly and that Overleaf's
History can undo it. When a direct edit touches a different file than the comment, or several files, the file name is
shown. The agent never resolves a thread: **a handled comment stays open until you resolve it**.

## The tools (MCP) and the CLI

| Tool | CLI | Does |
|---|---|---|
| `list_comments` | `list [--status s] [--all]` | Comments with selected text, request, thread, mode, `for_agent` |
| `show_comment` | `show ID` | One comment with its thread |
| `list_files`, `read_file` | | The project's text documents |
| `address_comment` | `address ID < edit.json` | Edits plus the reply, together; validated first |
| `create_file` | `create PROJECT PATH < content` | A NEW text file (and missing folders); never overwrites |
| `reply_to_comment` | `comments reply THREAD TEXT PROJECT` | Reply without editing |
| `list_tracked_changes` | `changes list PROJECT` | Pending tracked changes |
| `render_pdf` | `pdf PROJECT -o file.pdf` | Compile with Overleaf's compiler, save the PDF |

Other commands: `auth`, `init`, `doctor`, `check PROJECT`, `edit PROJECT FILE --old A --new B [--direct] [--dry-run]`,
`comments list PROJECT [--json]`. Run `olmcp help`. There is no command to resolve, reopen or delete a
thread, on purpose.

## Creating new files

The agent can add a new text file, for example `sections/related-work.tex`, with `create_file`. Missing folders are
created too. Only text files that Overleaf opens in its editor are created (`.tex .bib .sty .cls .bst .md .txt .csv` and a
few more); images and other binaries are not.

Three things to know. First, **a new file is not a tracked change**: Overleaf does not track file creation, so the file
exists at once, and you delete it in Overleaf if you do not want it. Second, the tool **never overwrites or deletes**:
a file or folder with that name is an error, and changes to existing files go through `address_comment`. Third, the
usual pattern is two calls in one reply: `create_file` for the new file and `address_comment` for the `\input` line that
uses it, which *is* a tracked change you can reject. After creating, the tool re-reads the project and checks that the
file exists with exactly the content sent.

## What `address_comment` enforces

- Every edit's `old` text must occur exactly once in the live document and must not overlap a pending change,
  except that it may lie entirely inside a suggestion of your own account, which revises it in place; otherwise
  nothing is written and the error says why.
- Several files: all are validated before any is written. The reply is posted only after the edits are in.
- A `#no-agent` comment is refused; a tag that disagrees with the agent's `mode` argument is refused.
- `read_file` returns the text as Overleaf stores it: pending suggestions are in, pending deletions are not shown.

## Limits

- Tracked changes are attributed to **your** Overleaf account (the tool acts with your cookie).
- Documents in Overleaf's newer history format are read but not edited yet.
- Unofficial interface: it can break when Overleaf changes, and the cookie expires after a few days.
- Overleaf's own warning applies: pushing from Git while tracked changes are pending can displace them. This tool
  does not use Git.
