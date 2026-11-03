// The agent-facing operations. Overleaf itself is the store: a comment's status, tags and history are all derived
// from its thread, so there is no local state to get out of sync.
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseTags, skipReasons, stripTags } from './tags.js';
import { parseProjectRef } from './project.js';
import { beforeAfter } from './textdiff.js';

export class ToolError extends Error {}
export const AGENT_PREFIX = '[agent] ';
const DIRECT_HINT = "\n\nThis was applied directly; Overleaf's History can undo it.";
const MAX_CHARS = 60000;

export function toItem(c, { commentTags = true } = {}) {
  const thread = (c.messages || []).map((m) => ({
    from: String(m.content ?? '').startsWith(AGENT_PREFIX) ? 'agent' : 'researcher',
    text: String(m.content ?? '').replace(AGENT_PREFIX, ''), raw: String(m.content ?? ''),
    author: m.user?.email || m.user?.name || m.user_id || '',
  }));
  const human = thread.filter((m) => m.from === 'researcher');
  if (human.length === 0) return null; // only agent messages: not a request
  let agent = null; let mode = null;
  for (const m of human) {
    const t = parseTags(m.raw, commentTags);
    if (t.agent !== null) agent = t.agent;
    if (t.mode) mode = t.mode;
  }
  const last = thread[thread.length - 1];
  const status = c.resolved ? 'resolved' : last.from === 'agent' ? 'addressed' : 'open';
  return {
    id: c.threadId, status, file: c.path, line: c.line, selected_text: c.selectedText,
    request: stripTags(human[0].raw), agent_tag: agent === true ? 'agent' : agent === false ? 'no-agent' : null,
    agent, mode, thread: thread.map(({ from, text, author }) => ({ from, text, author })),
  };
}

export class Tools {
  constructor(client, { project = null, mode = 'review', commentTags = true }) {
    this.client = client; this.defaultProject = project; this.defaultMode = mode; this.commentTags = commentTags;
    this.currentProject = project;
  }

  /** The same tools bound to the project the agent named (an id, a project URL or a git URL), if it named one. */
  forProject(ref) {
    if (!ref) {
      if (!this.defaultProject) throw new ToolError('no project is set for this folder: pass "project" (the Overleaf project id, project URL or git URL) with the call, or run "olmcp init <project-id>" here');
      return this;
    }
    let id;
    try { id = parseProjectRef(ref); } catch (e) { throw new ToolError(e.message); }
    const bound = new Tools(this.client, { project: id, mode: this.defaultMode, commentTags: this.commentTags });
    return bound;
  }

  get project() { return this.currentProject; }

  async items() {
    const comments = await this.client.listComments(this.project, { status: 'all' });
    return comments.map((c) => toItem(c, { commentTags: this.commentTags })).filter(Boolean);
  }

  present(item, skips) {
    const { agent, ...rest } = item;
    const why = skips[item.id];
    return { ...rest, mode: item.mode ?? this.defaultMode, mode_chosen_by_researcher: Boolean(item.mode), for_agent: !why, skipped_because: why ?? null };
  }

  async listComments({ status = 'open', include_skipped = false } = {}) {
    const items = await this.items();
    const skips = skipReasons(items);
    return items
      .filter((c) => status === 'all' || c.status === status)
      .filter((c) => include_skipped ? skips[c.id] !== 'no-agent' : !skips[c.id])
      .map((c) => this.present(c, skips));
  }

  async #get(id) {
    const items = await this.items();
    const item = items.find((c) => c.id === id);
    if (!item) throw new ToolError(`no comment ${id} (list_comments shows the ids)`);
    return { item, skips: skipReasons(items) };
  }

  async showComment(id) { const { item, skips } = await this.#get(id); return this.present(item, skips); }

  async listFiles() { return { files: await this.client.listFiles(this.project) }; }

  async readFile(path, { start_line, end_line } = {}) {
    let { content } = await this.client.readFile(this.project, path);
    if (start_line || end_line) {
      const lines = content.split('\n');
      content = lines.slice(Math.max(0, (start_line ?? 1) - 1), end_line ?? lines.length).join('\n');
    }
    const truncated = content.length > MAX_CHARS;
    return { path, content: truncated ? content.slice(0, MAX_CHARS) : content, truncated,
      note: 'Text carrying a pending tracked deletion is still present here.' };
  }

  async listTrackedChanges() { return { changes: await this.client.listChanges(this.project) }; }

  async renderPdf({ save_to } = {}) {
    const { pdf } = await this.client.renderPdf(this.project);
    const file = resolve(save_to || 'overleaf-output.pdf');
    writeFileSync(file, pdf);
    return { file, bytes: pdf.length, note: "Compiled by Overleaf's own compiler. Read the PDF to see the pages." };
  }

  async replyToComment(id, text) {
    const { item } = await this.#get(id);
    if (item.agent === false) throw new ToolError(`the researcher tagged ${id} #no-agent: do not work on it or reply to it`);
    if (!String(text || '').trim()) throw new ToolError('reply text is empty');
    await this.client.reply(this.project, id, AGENT_PREFIX + text.trim());
    return { comment_id: id, status: 'addressed', note: 'Replied in the thread; the researcher answers there.' };
  }

  async addressComment(id, edits, reply, mode) {
    const { item } = await this.#get(id);
    if (item.agent === false) throw new ToolError(`the researcher tagged ${id} #no-agent: do not work on it or reply to it`);
    if (item.status === 'resolved') throw new ToolError(`${id} is already resolved`);
    if (mode !== undefined && mode !== null && !['review', 'direct', 'suggest'].includes(mode)) throw new ToolError(`mode must be review or direct, got ${mode}`);
    const asked = mode === 'suggest' ? 'review' : mode;
    if (item.mode && asked && asked !== item.mode) {
      throw new ToolError(`the researcher asked for '${item.mode}' on ${id}, so it cannot be addressed in '${asked}' mode; omit mode to follow their choice`);
    }
    const editMode = item.mode || asked || this.defaultMode;
    if (!String(reply || '').trim()) throw new ToolError('a reply is required: say what you changed and why');
    if (!Array.isArray(edits) || edits.length === 0) throw new ToolError('at least one edit is required; to ask the researcher a question use reply_to_comment');
    const byFile = new Map();
    for (const e of edits) {
      if (!e?.file || !e.old || e.old === e.new) throw new ToolError('each edit needs a file and a non-empty "old" text that differs from "new"');
      byFile.set(e.file, [...(byFile.get(e.file) || []), { old: e.old, new: e.new ?? '' }]);
    }
    const tracked = editMode === 'review';
    try {
      for (const [file, group] of byFile) await this.client.editDocument(this.project, file, group, { tracked, dryRun: true });
      for (const [file, group] of byFile) await this.client.editDocument(this.project, file, group, { tracked });
    } catch (e) {
      throw new ToolError(`Overleaf did not take the edit: ${e.message}`);
    }
    // A tracked change is already shown by Overleaf (struck-through and added text with Accept/Reject), so the reply is
    // just the agent's words. A direct edit leaves no visible trace, so the reply shows what it said before and now.
    const changes = tracked ? '' : edits.map((e) => {
      const { before, after } = beforeAfter(e.old, e.new ?? '');
      return `\n\n${edits.length > 1 || e.file !== item.file ? `In ${e.file}:\n` : ''}Before: ${before}\nAfter:  ${after}`;
    }).join('');
    await this.client.reply(this.project, id, AGENT_PREFIX + reply.trim() + changes + (tracked ? '' : DIRECT_HINT));
    return { comment_id: id, status: 'addressed', mode: editMode, files: [...byFile.keys()],
      note: tracked ? 'Written into Overleaf as tracked changes; the researcher accepts or rejects them there.' : 'Applied as a plain edit in Overleaf.' };
  }
}
