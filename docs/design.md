# olmcp: design

How the current tool works and why. It is the Node program `olmcp` (also installed as `olmcp-overleaf`). The design
record of the earlier Python version, with the options it weighed, is kept in
[history/design-python.md](history/design-python.md).

Status tags: **[built]** exists and is tested against a fake Overleaf, **[verified]** the author has seen it work on a
real project, **[planned]** agreed but not built, **[open]** undecided. What is verified and what is not is tracked
in [status-and-roadmap.md](status-and-roadmap.md).

---

## 1. Problem

Overleaf holds your paper and your review comments; an AI agent cannot see either. Overleaf's Git integration (a
premium feature) carries only the files, not the comments or tracked changes, and the agent has no way to be told
"improve this paragraph" where you are already commenting. The goal is the shortest loop between **a comment in
Overleaf** and **a reviewable change in Overleaf**.

## 2. Goals and non-goals

Goals
- G1. Comment in Overleaf's Review panel; the agent receives the message, the selected text and the thread.
- G2. The agent's edit appears where you already review: as a **tracked change** with Accept and Reject. **[verified]**
- G3. The agent replies in the same thread, in plain words, and never closes it. **[verified]**
- G4. Per-comment, optional steering with hashtags; a default mode for the rest.
- G5. Nothing to install but one Node program; no paid Overleaf plan, no Git, no clone, no TeX, nothing hosted.
- G6. Any agent that can start a local MCP server (Claude Code, Codex, ...).

Non-goals
- Replacing the editor or real-time co-editing.
- Deciding *how* an agent should work for a kind of task. That belongs in the user's instructions.
- Hiding the fact that this rests on Overleaf's unofficial web interface.

## 3. Principles

1. **Overleaf is the store.** A comment's status, tags and history are derived from its thread. There is no local
   database, no files in your project, nothing to get out of sync.
2. **A connector, not a policy.** The tool gives the agent capabilities and honours what the researcher chose
   (tags, mode). Only what can be enforced in code is enforced; the rest is instruction text.
3. **The agent supplies words; the tool does the mechanics.** The agent says *which text becomes which text*; the
   tool finds it, builds the operations, sends them, checks the result and posts the reply.
4. **Never silently the wrong thing.** A tracked edit that Overleaf did not record as tracked is an error, not a
   plain edit. An edit that does not match exactly once is refused. A tag beats the agent's choice.
5. **No way to close a thread.** The client has no resolve, reopen or delete. A property of the code, tested.
6. **Small and dependency-free.** Plain Node 20+, a hand-written MCP server, nothing else to audit.

## 4. Architecture

```
 Overleaf (web)                                        your computer
 ┌──────────────────────┐    HTTPS + your session     ┌─────────────────────────┐   stdio    ┌───────┐
 │ project page (CSRF)  │ ◄───────── cookie ────────► │ olmcp                   │ ◄────────► │ agent │
 │ live-edit socket     │                             │  client · tools · mcp   │  (MCP)     └───────┘
 │ thread + compile API │                             └─────────────────────────┘
 └──────────────────────┘
```

| Module (`src/`) | Responsibility |
|---|---|
| `http.js` | `fetch` with a cookie jar and hand-followed redirects (so cookies set on the way are kept) |
| `socketio.js` | A Socket.IO 0.9 long-polling client: handshake, packets, acknowledged calls, heartbeat, close |
| `ranges.js` | Decode what Overleaf sends for a document; build comments and tracked changes from it |
| `client.js` | `OverleafClient`: connect (CSRF), list comments and changes, read files, edit, compile, reply |
| `tags.js` | `#agent`, `#no-agent`, `#review`/`#suggest`, `#direct`; focus and hands-off rules |
| `textdiff.js` | The Before/After shown for direct edits |
| `tools.js` | The agent-facing operations and their refusals (`ToolError`) |
| `mcp.js` | The MCP server: JSON-RPC over stdio |
| `project.js`, `config.js` | Which project (argument, file, variable, Git remote); where the cookie lives |
| `cli.js` | The commands (`auth`, `init`, `doctor`, `list`, `address`, `pdf`, `mcp`, ...) |

## 5. How the Overleaf side works  [built, partly verified]

There is no public API for comments or tracked changes, so the client does what Overleaf's own editor does.

- **Session.** Your `overleaf_session2` cookie, plus the CSRF token scraped from the `/project` page (needed for
  writes). An expired cookie shows up as the login form, and the error says so.
- **The live-edit socket.** Overleaf's editor uses Socket.IO 0.9 over long polling. The client opens it per project
  (`joinProjectResponse` carries the folder tree), joins a document (`joinDoc` returns the lines, the version, and
  the ranges: comments and tracked changes) and sends `applyOtUpdate`. One socket cannot overlap requests, so reading
  many documents uses a small pool of sockets.
- **Comments.** A comment's selected text and position come from the document's ranges; its messages come from the
  threads endpoint. The client reads both and joins them.
- **Edits.** An edit is a ShareJS operation list stamped with the document version: delete the old text, insert the
  new. Sent with a tracking id (`meta.tc`, an 18-hex seed, the same marker the editor uses in Reviewing mode), the
  server records a *tracked* deletion and insertion instead of changing the text. If someone else edited meanwhile the
  version no longer matches and Overleaf rejects the update.
- **What the stored text is.** For a normal (legacy) document the text Overleaf stores has every tracked insertion
  in it and every tracked deletion out: an insertion occupies its length, a deletion is a record `{d, p}` at one
  position. (This is how olcli's rejection logic treats it; the fake server models it the same way.)
- **Revising.** When `old` lies entirely inside a tracked insertion made by the same account (the `ol-user_id` of the
  page equals the change's user), the same delete-and-insert operations change the insertion in place: Overleaf shrinks
  the insertion by the deleted text and extends it by the inserted text, and records no deletion for your own
  text. The client then re-reads the document and requires the stored text to equal the expected text and no new
  deletion to have appeared. If Overleaf instead leaves the old suggestion as a struck-through deletion, the client
  errors and names what to reject. A revision is refused when mixed with new edits, in `direct` mode, or when the
  insertion is not provably the caller's.
- **Verification.** After a tracked edit the client re-joins the document and requires changes carrying its seed. If
  there are none it fails loudly, because the edit may have been applied as a plain one.
- **New files.** Missing folders are created with `POST /project/<id>/folder`, then the file is uploaded the way the
  editor's upload does (`POST /project/<id>/upload?folder_id=...`, multipart with the CSRF token); a text file with an
  editable extension becomes a document. File creation is not part of the tracked-change machinery, so it is
  immediate. The client refuses to overwrite, validates the path (no `..`, empty parts, backslashes, hidden names), limits
  the extension to editable text and the size to 1,000,000 characters, then re-reads the project and requires the
  document at that path with exactly the content sent.
- **PDF.** `POST /project/<id>/compile`, then download `output.pdf` (with the compile server id); on failure, the TeX
  log's error lines are returned.
- **Not supported.** Documents in Overleaf's newer history format are read but not edited; the client refuses rather
  than guess.

The approach follows [olcli](https://github.com/aloth/olcli) (MIT; see `THIRD_PARTY_NOTICES.md`). Writing tracked
changes is new here.

## 6. Comments, status and tags  [built]

Everything is read from the thread, so it is stateless.

- **Status.** `resolved` if the thread is resolved; `addressed` if the last message is the agent's (starts with
  `[agent] `); otherwise `open`. A researcher reply after the agent reopens it by itself.
- **The request** is the first researcher message with tags removed; later messages are follow-ups the agent sees.
- **Tags** (any researcher message, case-insensitive, not inside URLs; the latest message mentioning a tag decides):
  `#no-agent` hides the comment and makes the tools refuse it, always; `#agent` is focus: while any open comment has it
  only those are listed (advisory, the agent can be told otherwise); `#review` / `#suggest` mean tracked change;
  `#direct` means plain edit. Conflicts take the safe side: `#no-agent` over `#agent`, `#suggest`/`#review` over
  `#direct`. `commentTags: false` in `.olmcp.json` turns tag reading off.
- **Mode precedence.** The comment's tag, else the agent's `mode` argument, else the folder's default (`review`).
  A tag that disagrees with the agent's argument is refused with a message saying so.

## 7. The tools and what they enforce  [built]

`list_comments`, `show_comment`, `list_files`, `read_file`, `address_comment`, `reply_to_comment`,
`create_file`, `list_tracked_changes`, `render_pdf`; each takes an optional `project`. `address_comment(comment_id, edits, reply,
mode?)` is the one that matters:

1. Refuse `#no-agent`, resolved comments, a tag/mode clash, an empty reply or no edits. (A comment the researcher answered after the agent's suggestion is open again, so the agent can revise it.)
2. Validate every edit against the live document (a dry run per file): `old` must occur exactly once and must not
   overlap a pending change, unless it lies wholly inside a suggestion of the same account (a revision); several files are all checked before any is written.
3. Write the edits (tracked in `review`, plain in `direct`).
4. Post the reply, only now: an edit that failed never leaves a reply claiming it happened.

The reply is the agent's one to three sentences. In `review` nothing is added, because Overleaf already shows the
change. In `direct` a Before / After of the changed passage is appended, because a plain edit leaves no visible trace.

**Enforced in code:** validation above, `#no-agent`, tag precedence, no resolve/reopen/delete, the "tracked means
tracked" check. **Instruction only** (the server's own instructions and `AGENTS.md`): how to word replies, when to
ask instead of guess, not to reach Overleaf by other means. The tool does not claim to stop an agent that can read
your cookie file.

## 8. Which project  [built]

The tools take a `project` argument (an id, a project URL or a Git URL; the 24-hex id is extracted). If omitted: the
`--project` flag, `OVERLEAF_PROJECT`, `.olmcp.json` found in the folder or above (`olmcp init`), or the Git remote
of the current folder when its host is an Overleaf server. So there are two natural uses: name the project in the
chat (no setup), or work from a clone (the project is recognised). The clone is optional and never written to by the
tool: the live project is the only thing edited.

## 9. Security and privacy  [built]

- The cookie gives full access to the account. It is stored in `~/.config/olmcp/config.json` with mode 0600 (no
  effect on Windows) or read from `OVERLEAF_SESSION`; it is never printed, logged or put in an error (a test checks
  every command's output).
- Document text and comments go to the agent you chose, as with any MCP tool. Nothing goes anywhere else; nothing is
  hosted.
- Comment text is data, not instructions: the server's instructions say so, and the tools carry no capability beyond
  the listed ones.
- Tracked changes carry **your** Overleaf identity, because the tool acts with your cookie.

## 10. Failure modes

| Failure | Behaviour |
|---|---|
| Cookie expired or missing | A clear error; `olmcp doctor` says what to do |
| `old` text not found / found more than once | Nothing written; the error says how to retry |
| `old` overlaps a pending change (not wholly inside your own suggestion) | Refused; accept or reject that change first, or edit only inside your own suggestion |
| A revision leaves the old suggestion as a tracked deletion | Error naming what to reject; nothing else written |
| Document edited by someone meanwhile | Overleaf rejects the stale version; nothing written |
| Overleaf did not record the edit as tracked | Error, no reply posted, check History |
| `create_file` onto an existing name, an unsafe path, a non-text extension | Refused before anything is created |
| The upload succeeds but the document is missing or its text differs | Error naming the path; nothing is deleted (the researcher decides) |
| Several-file edit fails part-way | The error names what was already written |
| Document in the newer history format | Read allowed, edit refused |
| Overleaf changes its unofficial interface | Calls fail with HTTP errors; the fake-server tests cannot catch it |
| Rate limiting on the socket (HTTP 429) | Extra sockets are dropped, reading continues on fewer |

## 11. Decisions and the alternatives they replaced

| Decision | Instead of | Why |
|---|---|---|
| Talk to Overleaf's web interface with a session cookie | Git sync, GitHub sync + CI | Comments and tracked changes are not in Git; no premium plan or manual push/pull; no round trip through a CI run |
| Overleaf is the store; derive status from threads | Comment files in the repo | Nothing to sync, nothing in the paper's repo; the reply is the state |
| Tracked changes (`review`) as the default | A held branch plus a generated `redline.tex` | Overleaf already has a review UI with Accept and Reject; the redline was a workaround for not having it |
| A hand-written MCP server | The official SDK | No dependencies; a small, well-specified protocol; cross-tested with the official Python client |
| `old`/`new` text edits | Offsets or patches from the agent | Agents are good at wording, bad at positions; the tool computes and verifies positions |
| No resolve/reopen/delete | An opt-in "auto resolve" | The researcher decides when a thread is done; an agent that can close threads hides its own work |
| Node, not Python | Python plus Node (`olcli`) | The one hard piece (the live-edit protocol) is JavaScript-shaped; one language and one install |
| The Python tool retired to `python-legacy` | Porting Git sync, markers, `redline.tex` | `review` covers the main use; those can be ported if someone needs them |

## 12. Open questions

| Question | Where it stands |
|---|---|
| Real-Overleaf behaviour of `#direct`, `#no-agent`, `#agent`, `render_pdf`, subfolders | Built and tested against the fake; the [alpha test plan](alpha-test-plan.md) covers them |
| `create_file` on the real service | Built and tested against the fake; the upload endpoint is the one olcli uses (alpha test plan scenario 12) |
| Revising a suggestion in place on the real service | Built and tested against the fake; depends on Overleaf's ranges tracker removing your own inserted text instead of striking it (alpha test plan scenario 11) |
| Trim the unchanged start and end of each edit so a tracked change covers only the changed words | **[planned]** |
| Deleting or renaming files, binary uploads | **[open]** deliberately not offered: they cannot be undone through a tracked change |
| Tracked changes under the agent's own name | **[open]** Overleaf has one identity per cookie; a second account would need its own cookie |
| Editing documents in the newer history format | **[open]** needs a different operation format |
| Many-document projects: every call joins every document | **[open]** caching, or joining only the document a comment is in |
| Agents that cannot read PDFs | **[planned]** page images |
| ChatGPT chat apps | **[open]** needs a remote HTTPS server with real authentication |
| Windows | **[open]** untested; the code has nothing OS-specific |
| Reviving Git sync, `%% @agent:` markers or per-hunk decisions | **[open]** they exist in `python-legacy`; port on demand |
