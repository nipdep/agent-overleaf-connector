# Alpha test plan

For anyone trying the alpha on their own project and computer. About 20 minutes. Use a **scratch project** first
(copy a paper into a new Overleaf project), not your real paper. Everything the agent does is a tracked change you can
reject, except `direct` mode, which you can undo with Overleaf's History.

## Install and check

```bash
npm install -g github:nipdep/agent-overleaf-connector#main
olmcp --version                     # 1.0.0-alpha.3 or later
olmcp auth --cookie "<overleaf_session2 value>"
olmcp doctor --project <project-id>  # all [ok]
claude mcp add --scope user olmcp -- "$(which olmcp)" mcp   # and/or: codex mcp add olmcp -- "$(which olmcp)" mcp
```

If you had the old Python tool: `pipx uninstall agent-overleaf-connector` first. Restart the agent after registering.

## Scenarios

Tell the agent: "Address the review comments in <project URL>". Tick what behaves as described.

| # | Do in Overleaf | Expect |
|---|---|---|
| 1 | Select a sentence, comment "make this shorter" | The sentence shows a tracked deletion and insertion; the thread has an `[agent]` reply of one to three plain sentences; the thread is still open |
| 2 | Click Reject on that change | The original text is back |
| 3 | Comment "make this clearer #direct" | The text changes with no tracking; the reply shows Before/After |
| 4 | Comment "ignore this one #no-agent" next to two ordinary comments | The agent does not touch or answer it |
| 5 | Two ordinary comments plus one with `#agent` | The agent works on the `#agent` one first/only |
| 6 | Reply in an answered thread: "not like that, try again" | The thread counts as open again and the agent addresses it |
| 7 | Comment on text inside a file in a folder, and on text after an emoji or accent | Edits land in the right place |
| 8 | Ask the agent "compile the paper and tell me if there are errors" | A PDF is saved; a deliberate TeX error is reported with its line |
| 9 | Comment with no selected text (a general comment) | The agent asks or replies; it does not guess an edit |
| 10 | Leave the tool unused for a few days | `olmcp doctor` says the cookie expired; `olmcp auth` fixes it |
| 11 | After the agent's suggestion, reply in the thread "shorter please" (do not accept or reject) | The agent revises: the suggestion's new text changes in place, the original is still the one pending deletion, and you can still accept or reject it as a single change; no struck-through leftovers of the first suggestion |
| 12 | Comment "move the related-work paragraph into its own file" | A new file appears in the right folder with the right content, and an `\input` line in the original file is a tracked change; creating a file that already exists is refused, never overwritten |

## What to send back

Use the bug report template. Include `olmcp --version`, your OS, Node version (`node --version`), which agent, the
scenario number, what you expected and saw, and `olmcp doctor`. **Remove cookies, names and emails.** A screenshot of
the Overleaf Review panel helps a lot.
