# Alpha test plan

Use this checklist when trying `olmcp` on a new computer, agent, or Overleaf environment. It takes about 20 minutes.

Start with a disposable Overleaf project, not an important paper. Most edits are tracked and rejectable, but `#direct` edits and new-file creation happen immediately.

## Prepare

Complete the [setup guide](setup.md), then check the installed version and connection:

```bash
npm install -g github:nipdep/agent-overleaf-connector#main
olmcp --version
olmcp doctor --project <project-id>
```

Restart the MCP client after installing or updating. If the retired Python tool is still present, remove it with `pipx uninstall agent-overleaf-connector` before reinstalling.

Create a scratch project with:

- At least two `.tex` files, one inside a folder.
- A sentence containing an accented character or emoji.
- A paper that compiles successfully.

Tell the agent:

> Address the review comments in &lt;project URL&gt;.

## Core review behavior

| # | Try this in Overleaf | Expected result |
|---|---|---|
| 1 | Select a sentence and comment “make this shorter” | Overleaf shows a tracked deletion and insertion; the thread receives a short `[agent]` reply and stays open |
| 2 | Reject the proposed change | The original text returns |
| 3 | Accept a proposed change | The proposed text remains and the thread still closes only when you resolve it |
| 4 | Reply to an answered thread with “try again” | The thread becomes open and the agent handles the follow-up |
| 5 | Leave a general comment without selected text | The agent asks or replies instead of guessing an unsafe edit |

## Modes and scope controls

| # | Try this in Overleaf | Expected result |
|---|---|---|
| 6 | Comment “make this clearer #direct” | The text changes without tracking; the reply shows Before/After and mentions Overleaf History |
| 7 | Add `#no-agent` to one thread beside ordinary threads | The protected thread is neither listed nor answered |
| 8 | Add `#agent` to one thread beside ordinary threads | The focused thread is handled first or exclusively in the normal list |
| 9 | Comment on text in a subfolder and after an emoji or accent | The edit lands in the correct file and position |

## Recent features

| # | Try this in Overleaf | Expected result |
|---|---|---|
| 10 | Before accepting or rejecting a proposal, reply “shorter please” | The proposed insertion changes in place; the original remains the one pending deletion, with no leftover tracked deletion of the first proposal |
| 11 | Ask to move a paragraph into `sections/related-work.tex` | The new file appears immediately; the `\input` edit is tracked separately; an existing path is never overwritten |
| 12 | Ask the agent to compile the paper | Overleaf compiles it and the MCP saves a PDF; a deliberate TeX error is reported clearly |

## Expiration and recovery

After the session cookie expires, `olmcp doctor` should report the problem clearly. Storing a fresh `overleaf_session2` value with `olmcp auth` should restore access.

## Report the result

For a bug, include:

- `olmcp --version` and `node --version`.
- Operating system and MCP client.
- Scenario number.
- What you expected and what happened.
- Redacted `olmcp doctor` output.

A screenshot of the Review panel is useful. Remove the session cookie, project text, names, email addresses, and private project IDs before sharing anything.
