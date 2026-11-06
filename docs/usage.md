# Use `olmcp`

The normal loop has three participants:

```text
you ask in Overleaf → the agent proposes through olmcp → you decide in Overleaf
```

There is no pull or push step. The MCP reads and edits the live Overleaf project.

## The daily review loop

1. In Overleaf, select text and leave a Review comment.
2. Tell the agent, “Address the review comments.”
3. The agent reads the comment, the selected text, its thread, and the current file.
4. The agent proposes an edit and replies in the same thread.
5. You accept or reject the tracked change, reply with a follow-up, or resolve the thread.

The agent never resolves the discussion for you.

## What a proposed edit means

The default mode is `review`. In this mode, Overleaf records two related changes:

- A tracked deletion containing your original text.
- A tracked insertion containing the agent's proposed text.

Nothing is finally accepted until you use Overleaf's **Accept** button. **Reject** restores the original text.

The thread reply is intentionally short because the Review panel already shows the exact change:

```text
[agent] Shortened the sentence and removed the repeated claim.
```

Tracked changes are attributed to your Overleaf account. `olmcp` uses your session and cannot create a separate identity for the agent.

## Choose between review and direct edits

| Mode | What happens | How to undo or decide |
|---|---|---|
| `review` (default) | The edit appears as a tracked deletion and insertion | Accept or reject it in Overleaf |
| `direct` | The live text changes immediately, without tracked-change controls | Use Overleaf History |

Use `review` for normal work. Use `direct` only when you intentionally want an immediate edit.

The default mode comes from `.olmcp.json` or `OLMCP_MODE`. A tag on a comment takes precedence over the default and over the agent's requested mode.

## Comment tags

Tags are optional and may appear anywhere in one of your messages.

| Tag | Meaning |
|---|---|
| `#review` or `#suggest` | Propose a tracked change |
| `#direct` | Apply a plain edit immediately |
| `#no-agent` | Hide this thread from the agent and refuse edits or replies to it |
| `#agent` | Focus the normal comment list on tagged threads while any remain open |

Examples:

```text
Make this claim more cautious. #review
Fix the typo directly. #direct
This is a note for my coauthor. #no-agent
Handle these two comments first. #agent
```

If tags conflict, the safer choice wins: `#no-agent` beats `#agent`, and review beats direct. The most recent message from you that mentions a tag sets the thread's current choice. Tags are removed from the request shown to the agent.

`#no-agent` is enforced. `#agent` is a focus filter, not an access-control boundary; you may still explicitly ask an agent to include skipped comments. Set `"commentTags": false` in `.olmcp.json` if you do not want tags parsed.

## Comment status

The connector does not keep a separate review database. It derives status from the Overleaf thread:

| Status | Meaning |
|---|---|
| `open` | Your message is the latest and needs an agent response |
| `addressed` | The latest message is the agent's reply |
| `resolved` | You resolved the thread in Overleaf |

Replying after the agent makes the thread `open` again automatically.

## Ask for another version of a pending suggestion

You do not need to accept or reject the first proposal. Reply in the same thread with something like “shorter please” or “keep the first sentence,” then ask the agent to address comments again.

The connector shows the agent the pending changes near that comment. The agent can replace the text inside its own pending insertion, while the paper's original wording remains the pending deletion. You still see one proposal to accept or reject.

This revision works only when:

- The edit is in `review` mode.
- The insertion was created through the same Overleaf account.
- The call contains the revision only, not unrelated new edits.

If those conditions are not met, the MCP refuses the request instead of stacking an unsafe edit on another change.

## Create a new file

The `create_file` tool can add a new editable text file and any missing folders. A typical request is:

> Move this related-work section into `sections/related-work.tex` and include it here.

The safe sequence is:

1. The agent creates `sections/related-work.tex`. The file appears immediately.
2. The agent separately proposes the `\input{sections/related-work}` edit in an existing file.
3. You review the new file directly and accept or reject the `\input` change.

Overleaf cannot represent file creation as a tracked change. For that reason, `olmcp` never overwrites or deletes an existing path. If you do not want the new file, delete it yourself in Overleaf.

Supported files are editable text formats such as `.tex`, `.bib`, `.sty`, `.cls`, `.bst`, `.md`, `.txt`, `.csv`, `.json`, `.yml`, and `.yaml`. Hidden files, unsafe paths, binary formats, and content over 1,000,000 characters are refused.

The equivalent CLI command reads the content from standard input:

```bash
olmcp create <project-id> sections/related-work.tex < related-work.tex
```

Add `--dry-run` to validate the path without creating anything.

## What the MCP can do

The MCP exposes nine tools. Every tool accepts a `project` value—a 24-character ID, an Overleaf project URL, or an Overleaf Git URL—but it may be omitted when the server already has a project from `.olmcp.json` or its startup options.

| Tool | What it gives the agent | Does it change Overleaf? |
|---|---|---|
| `list_comments` | Open comments, selected text, requests, status, mode, and thread context | No |
| `show_comment` | One complete thread and nearby pending changes | No |
| `list_files` | Paths of editable text documents | No |
| `read_file` | Live document text, with pending insertions visible and pending deletions omitted | No |
| `address_comment` | Validated edits plus one reply to the thread | Yes |
| `create_file` | One new text file and missing folders | Yes, immediately |
| `reply_to_comment` | A reply or question without an edit | Yes, reply only |
| `list_tracked_changes` | Pending tracked insertions and deletions | No |
| `render_pdf` | A PDF compiled by Overleaf and saved on the local computer | Compiles, but does not edit project files |

`address_comment` checks that each `old` passage appears exactly once in the live document. It validates every file first, then writes the changes, and posts the reply only after the edits succeed. A failure during a multi-file write can leave an earlier file changed; the error reports what happened.

## What the MCP cannot do

There is no MCP tool or CLI command to:

- Accept or reject a tracked change.
- Resolve, reopen, close, or delete a comment thread.
- Overwrite or delete an existing file.
- Create a binary file such as an image.
- Edit a document that uses the unsupported newer Overleaf history format.
- Monitor a project continuously or react to comments in the background.
- Synchronize a local Git clone.
- Give edits an identity different from the account represented by the session cookie.

These omissions are deliberate. Decisions that hide or finalize work stay with the researcher in Overleaf.

## Useful CLI commands

Most people use the MCP through an agent. The CLI is useful for setup and diagnosis:

| Command | Purpose |
|---|---|
| `olmcp auth --cookie VALUE` | Store an Overleaf session |
| `olmcp init PROJECT --mode review` | Save a project and write agent instructions in the current folder |
| `olmcp doctor` | Check Node, credentials, project selection, and comment access |
| `olmcp check PROJECT` | Confirm that comment threads are readable |
| `olmcp comments list PROJECT` | List comment threads directly |
| `olmcp changes list PROJECT` | List pending tracked changes |
| `olmcp pdf PROJECT -o output.pdf` | Compile and save the PDF |
| `olmcp create PROJECT PATH < file` | Create a new text file without overwriting |
| `olmcp mcp` | Run the local MCP server over standard input/output |

Run `olmcp help` for the complete command syntax.

## Limits to keep in mind

- The connector uses an unofficial Overleaf interface and may need updates when Overleaf changes.
- The browser session cookie expires periodically.
- Every call currently joins every document, so very large projects may be slower.
- Overleaf warns that Git pushes can disrupt pending tracked changes. Avoid pushing from Git until review changes are decided.
- The newer Overleaf document-history format is read-only through this connector for now.

For the security boundary around agents and shell access, read [Connect an AI agent](agents.md#security-and-trust).
