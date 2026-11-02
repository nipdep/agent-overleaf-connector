# review/

Managed by paper-review. You can ignore everything here except `redline.tex`.

- **`redline.tex`**: the agent's pending changes, shown as a redline. In Overleaf choose
  *Menu → Main document → `review/redline.tex`* to see it in the PDF preview. To decide, edit
  only the `%% decision[...]` lines (and optionally `%% reason[...]`):
  set `accept` or `reject`, then push to GitHub. Switch the main document back afterwards.
- `comments/`: one JSON file per review comment.
- `CHANGELOG.md`: generated list of what changed and why.
- `redline.json`, `assets/`: machine files the redline needs.

To ask the agent for a change, add a line in your text before the paragraph:

```
%% @agent: soften this claim and cite a source
```
