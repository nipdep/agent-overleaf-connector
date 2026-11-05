// Overleaf client: comments, replies and tracked-change edits. Deliberately has no way to resolve, reopen or
// delete a comment thread: that stays with the researcher.
import { randomBytes } from 'node:crypto';
import { Jar, request } from './http.js';
import { ProjectSocket } from './socketio.js';
import { collectDocs, commentsFromDocs, normalizeJoined, sharejsChanges } from './ranges.js';

const csrfFrom = (html) =>
  /<meta[^>]+name=["']ol-csrfToken["'][^>]+content=["']([^"']+)["']/i.exec(html)?.[1]
  || /<meta[^>]+content=["']([^"']+)["'][^>]+name=["']ol-csrfToken["']/i.exec(html)?.[1]
  || /name=["']_csrf["'][^>]+value=["']([^"']+)["']/i.exec(html)?.[1];

/** Text files Overleaf opens in its editor (the rest would be stored as opaque uploads, which this tool does not create). */
export const EDITABLE_EXTENSIONS = new Set(['tex', 'bib', 'sty', 'cls', 'bst', 'bbx', 'cbx', 'def', 'cfg', 'ltx', 'dtx', 'ins', 'ist', 'lco', 'txt', 'md', 'csv', 'tsv', 'json', 'yml', 'yaml']);
export const MAX_NEW_FILE_CHARS = 1_000_000;

/** A safe relative path for a new document, or an Error saying what is wrong with it. */
export function checkNewFilePath(path) {
  if (typeof path !== 'string' || !path.trim()) throw new Error('path is empty');
  const clean = path.trim().replace(/^\/+/, '');
  if (/[\\\u0000-\u001f]/.test(clean) || clean.endsWith('/')) throw new Error(`"${path}" is not a valid file path (use forward slashes, no trailing slash)`);
  const parts = clean.split('/');
  if (parts.some((p) => p === '' || p === '.' || p === '..')) throw new Error(`"${path}" must not contain empty, "." or ".." parts`);
  if (parts.some((p) => p.length > 100) || clean.length > 300) throw new Error(`"${path}" is too long`);
  const name = parts[parts.length - 1];
  if (name.startsWith('.')) throw new Error(`"${name}": hidden files are not created`);
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
  if (!EDITABLE_EXTENSIONS.has(ext)) throw new Error(`"${name}": only text files Overleaf can edit are created (${[...EDITABLE_EXTENSIONS].map((e) => `.${e}`).join(' ')})`);
  return { path: clean, dirs: parts.slice(0, -1), name };
}

const userIdFrom = (html) =>
  /<meta[^>]+name=["']ol-user_id["'][^>]+content=["']([^"']+)["']/i.exec(html)?.[1]
  || /<meta[^>]+content=["']([^"']+)["'][^>]+name=["']ol-user_id["']/i.exec(html)?.[1] || null;

export class OverleafClient {
  constructor({ baseUrl, jar, csrf, userId = null }) { this.baseUrl = baseUrl; this.jar = jar; this.csrf = csrf; this.userId = userId; }

  static async connect({ baseUrl, sessionCookie, cookieName = 'overleaf_session2' }) {
    if (!sessionCookie) throw new Error('no Overleaf session cookie: run "olmcp auth --cookie <value>" or set OVERLEAF_SESSION');
    const jar = new Jar({ [cookieName]: sessionCookie });
    const res = await request(jar, `${baseUrl}/project`);
    if (!res.ok) throw new Error(`Overleaf answered HTTP ${res.status} (is the session cookie current?)`);
    if (/name=["']loginForm["']|name=["']password["']/.test(res.text)) throw new Error('the session cookie has expired: run "olmcp auth --cookie <value>" again');
    const csrf = csrfFrom(res.text);
    if (!csrf) throw new Error('could not find the CSRF token (session expired, or Overleaf changed its page)');
    return new OverleafClient({ baseUrl, jar, csrf, userId: userIdFrom(res.text) });
  }

  headers(json = false) {
    return { 'X-Csrf-Token': this.csrf, ...(json ? { 'Content-Type': 'application/json' } : {}) };
  }

  openSocket(projectId) { return new ProjectSocket(this.jar, this.baseUrl, projectId).open(); }

  async threads(projectId) {
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/threads`, { headers: this.headers() });
    if (!res.ok) throw new Error(`could not fetch comment threads: HTTP ${res.status}`);
    return JSON.parse(res.text);
  }

  async join(socket, docId, { history = true } = {}) {
    const args = await socket.rpc('joinDoc', [docId, { encodeRanges: true, supportsHistoryOT: history }]);
    return normalizeJoined(docId, args);
  }

  /** Join every document over a few sockets (one socket cannot overlap requests). */
  async joinAll(projectId, docs, first, concurrency = 4) {
    const joined = new Array(docs.length);
    let next = 0; let failure;
    const work = async (socket) => {
      try {
        while (failure === undefined && next < docs.length) {
          const i = next++;
          try { joined[i] = await this.join(socket, docs[i].id); } catch (e) { failure ??= e; }
        }
      } finally { await socket.close(); }
    };
    const extra = Array.from({ length: Math.max(0, Math.min(concurrency, docs.length) - 1) }, async () => {
      let socket;
      try { socket = await this.openSocket(projectId); } catch (e) { if (e.status !== 429) failure ??= e; return; }
      await work(socket);
    });
    await Promise.allSettled([work(first), ...extra]);
    if (failure !== undefined) throw failure;
    return joined;
  }

  async listComments(projectId, { status = 'all' } = {}) {
    const first = await this.openSocket(projectId);
    const docs = collectDocs(first.project);
    const threads = await this.threads(projectId);
    const joined = await this.joinAll(projectId, docs, first);
    return commentsFromDocs(docs, joined, threads, status);
  }

  async listChanges(projectId) {
    const first = await this.openSocket(projectId);
    const docs = collectDocs(first.project);
    const joined = await this.joinAll(projectId, docs, first);
    const out = [];
    docs.forEach((doc, i) => {
      if (joined[i].type !== 'sharejs-text-ot') return;
      for (const c of sharejsChanges(joined[i].ranges)) out.push({ docId: doc.id, path: doc.path, ...c });
    });
    return out;
  }

  /** Compile the project with Overleaf's own compiler (the same TeX Live version as your editor). */
  async compile(projectId, { draft = false } = {}) {
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/compile?enable_pdf_caching=true`, {
      method: 'POST', headers: this.headers(true), timeoutMs: 240000,
      body: JSON.stringify({ rootDoc_id: null, draft, check: 'silent', incrementalCompilesEnabled: true }),
    });
    if (!res.ok) throw new Error(`could not start a compile: HTTP ${res.status}`);
    const data = JSON.parse(res.text);
    const qs = data.clsiServerId ? `?clsiserverid=${encodeURIComponent(data.clsiServerId)}` : '';
    const file = (name, type) => (data.outputFiles || []).find((f) => f.path === name) || (type && (data.outputFiles || []).find((f) => f.type === type));
    const pdf = file('output.pdf', 'pdf');
    const log = file('output.log', 'log');
    return { status: data.status, pdfUrl: pdf ? `${this.baseUrl}${pdf.url}${qs}` : null, logUrl: log ? `${this.baseUrl}${log.url}${qs}` : null };
  }

  async download(url) {
    const res = await request(this.jar, url, { headers: this.headers(), timeoutMs: 120000 });
    if (!res.ok) throw new Error(`download failed: HTTP ${res.status}`);
    return res.buffer;
  }

  /** Compile and fetch the PDF; on a failed compile the error carries the first lines of the TeX log. */
  async renderPdf(projectId, options = {}) {
    const result = await this.compile(projectId, options);
    if (result.status !== 'success' || !result.pdfUrl) {
      let excerpt = '';
      if (result.logUrl) {
        try {
          const log = (await this.download(result.logUrl)).toString('utf-8');
          excerpt = log.split('\n').filter((l) => l.startsWith('!') || /error/i.test(l)).slice(0, 12).join('\n');
        } catch { /* the log is a courtesy */ }
      }
      throw new Error(`the compile did not succeed (${result.status})${excerpt ? `:\n${excerpt}` : ''}`);
    }
    return { status: result.status, pdf: await this.download(result.pdfUrl) };
  }

  async listFiles(projectId) {
    const socket = await this.openSocket(projectId);
    try { return collectDocs(socket.project).map((d) => d.path).sort(); } finally { await socket.close(); }
  }

  /** The stored text of one document: pending tracked insertions are in it, pending tracked deletions are not. */
  async readFile(projectId, path) {
    const socket = await this.openSocket(projectId);
    try {
      const wanted = path.replace(/^\/+/, '');
      const doc = collectDocs(socket.project).find((d) => d.path === wanted);
      if (!doc) throw new Error(`no document ${wanted} in the project (list_files shows the paths)`);
      const joined = await this.join(socket, doc.id);
      return { path: wanted, content: joined.content };
    } finally { await socket.close(); }
  }

  async createFolder(projectId, parentId, name) {
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/folder`, {
      method: 'POST', headers: this.headers(true), body: JSON.stringify({ parent_folder_id: parentId, name }),
    });
    if (res.status === 400) throw new Error(`could not create the folder "${name}" (it may already exist)`);
    if (!res.ok) throw new Error(`could not create the folder "${name}": HTTP ${res.status}`);
    return JSON.parse(res.text)._id;
  }

  /**
   * Create a new text document (and any missing folders) with the given content. Never overwrites: an existing
   * file or folder of that name is an error. A new file is not a tracked change (Overleaf does not track file
   * creation), so it appears at once; the researcher can delete it in Overleaf.
   */
  async createFile(projectId, path, content, { dryRun = false } = {}) {
    const target = checkNewFilePath(path);
    if (typeof content !== 'string') throw new Error('content must be a string');
    if (content.length > MAX_NEW_FILE_CHARS) throw new Error(`content is larger than ${MAX_NEW_FILE_CHARS} characters`);
    const socket = await this.openSocket(projectId);
    let folder; const createdFolders = [];
    try {
      const root = socket.project.rootFolder?.[0];
      if (!root?._id) throw new Error('could not read the project\'s folder tree');
      folder = root;
      const missing = [];
      for (const seg of target.dirs) {
        const next = missing.length ? null : (folder.folders || []).find((f) => f.name === seg);
        if (next) folder = next; else missing.push(seg);
      }
      if (!missing.length) {
        const taken = [...(folder.docs || []), ...(folder.fileRefs || []), ...(folder.folders || [])].some((e) => e.name === target.name);
        if (taken) throw new Error(`${target.path} already exists; this tool never overwrites a file (use address_comment to edit it)`);
      }
      if (dryRun) return { path: target.path, created: false, would_create_folders: missing, bytes: Buffer.byteLength(content) };
      for (const seg of missing) {
        const id = await this.createFolder(projectId, folder._id, seg);
        createdFolders.push(seg);
        folder = { _id: id, name: seg, folders: [], docs: [], fileRefs: [] };
      }
    } finally { await socket.close(); }
    const form = new FormData();
    form.append('targetFolderId', folder._id);
    form.append('name', target.name);
    form.append('type', 'text/plain');
    form.append('qqfile', new Blob([content], { type: 'text/plain' }), target.name);
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/upload?folder_id=${encodeURIComponent(folder._id)}`, {
      method: 'POST', headers: this.headers(), body: form, timeoutMs: 60000,
    });
    let data = null; try { data = JSON.parse(res.text); } catch { /* not JSON */ }
    if (!res.ok || data?.success === false) {
      throw new Error(`Overleaf did not create ${target.path}: ${data?.error || `HTTP ${res.status}`}${createdFolders.length ? ` (folders already created: ${createdFolders.join(', ')})` : ''}`);
    }
    // Verify: the document exists at that path with exactly this content.
    const check = await this.openSocket(projectId);
    try {
      const doc = collectDocs(check.project).find((d) => d.path === target.path);
      if (!doc) throw new Error(`Overleaf accepted the upload but ${target.path} is not an editable document in the project (check the project in Overleaf)`);
      const joined = await this.join(check, doc.id, { history: false });
      if (joined.content !== content) throw new Error(`${target.path} was created but its stored text differs from what was sent (${joined.content.length} vs ${content.length} characters); check it in Overleaf`);
    } finally { await check.close(); }
    return { path: target.path, created: true, folders_created: createdFolders, bytes: Buffer.byteLength(content) };
  }

  async reply(projectId, threadId, content) {
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/thread/${threadId}/messages`, {
      method: 'POST', headers: this.headers(true), body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`could not post the reply: HTTP ${res.status}`);
    try { return JSON.parse(res.text); } catch { return null; }
  }

  /**
   * Edit a document as tracked changes ("Reviewing" mode): each edit becomes a tracked deletion of `old` and a
   * tracked insertion of `new`, which the researcher accepts or rejects in Overleaf.
   *
   * Revising: if `old` lies entirely inside a tracked insertion made by this same account (the "temporary text" of
   * an earlier suggestion), the edit changes that text in place: Overleaf shrinks or extends the insertion, the
   * original deletion stays pending, and nothing has to be accepted or rejected first. Such revisions cannot be
   * mixed with new edits in one call, and are verified by re-reading the document.
   *
   * Refuses an edit whose `old` text is not found exactly once, or that overlaps any other tracked change.
   * With `tracked: false` the edit is applied directly (an ordinary edit).
   */
  async editDocument(projectId, path, edits, { tracked = true, dryRun = false } = {}) {
    const socket = await this.openSocket(projectId);
    try {
      const wanted = path.replace(/^\/+/, '');
      const doc = collectDocs(socket.project).find((d) => d.path === wanted);
      if (!doc) throw new Error(`no document ${wanted} in the project (paths like sections/intro.tex)`);
      const joined = await this.join(socket, doc.id, { history: false });
      if (joined.type !== 'sharejs-text-ot') throw new Error(`${wanted} uses Overleaf's newer document format, which this tool cannot edit yet; nothing was changed`);
      const pending = sharejsChanges(joined.ranges);
      // The stored text is the text with every pending insertion in and every pending deletion out, so an insertion
      // occupies its length and a deletion occupies no space (it sits at one position).
      const inserts = pending.filter((c) => c.kind === 'insert');
      const deletes = pending.filter((c) => c.kind === 'delete');
      const plan = edits.map((e, n) => {
        if (typeof e.old !== 'string' || typeof e.new !== 'string' || !e.old) throw new Error(`edit ${n + 1}: "old" and "new" must be strings and "old" must not be empty`);
        const first = joined.content.indexOf(e.old);
        if (first < 0) throw new Error(`edit ${n + 1}: the old text was not found in ${wanted}`);
        if (joined.content.indexOf(e.old, first + 1) >= 0) throw new Error(`edit ${n + 1}: the old text appears more than once in ${wanted}; include more context`);
        const end = first + e.old.length;
        const inside = inserts.find((c) => c.position <= first && end <= c.position + c.text.length);
        if (inside) {
          if (!tracked) throw new Error(`edit ${n + 1}: that text is a pending tracked insertion; revise it in review mode, or accept or reject it in Overleaf first`);
          if (!this.userId || inside.userId !== this.userId) {
            throw new Error(`edit ${n + 1}: that text is inside a tracked insertion that is not provably yours (it was made by someone else, or the author is unknown); accept or reject it in Overleaf first`);
          }
          return { pos: first, old: e.old, new: e.new, revise: true };
        }
        const clash = inserts.find((c) => c.position < end && c.position + c.text.length > first)
          || deletes.find((c) => first < c.position && c.position < end);
        if (clash) throw new Error(`edit ${n + 1}: that text overlaps a tracked change (${clash.kind}); accept or reject it in Overleaf first, or edit only inside a suggestion of your own`);
        return { pos: first, old: e.old, new: e.new, revise: false };
      });
      if (plan.some((e) => e.revise) && plan.some((e) => !e.revise)) {
        throw new Error('one call cannot both revise a pending suggestion and make new edits; do them in two calls');
      }
      plan.sort((a, b) => a.pos - b.pos);
      for (let i = 1; i < plan.length; i++) if (plan[i].pos < plan[i - 1].pos + plan[i - 1].old.length) throw new Error('two edits overlap');
      // Highest position first, so earlier positions stay valid within one update.
      const ops = [];
      for (const e of [...plan].reverse()) {
        if (tracked) {
          if (e.new) ops.push({ i: e.new, p: e.pos + e.old.length });
          ops.push({ d: e.old, p: e.pos });
        } else {
          ops.push({ d: e.old, p: e.pos });
          if (e.new) ops.push({ i: e.new, p: e.pos });
        }
      }
      const revising = plan.length > 0 && plan[0].revise;
      const seed = randomBytes(9).toString('hex'); // 18 hex characters; the server appends a counter
      const update = { doc: doc.id, op: ops, v: joined.version, ...(tracked ? { meta: { tc: seed } } : {}) };
      if (dryRun) return { path: wanted, tracked, ops, revising, applied: false };
      await socket.rpc('applyOtUpdate', [doc.id, update]);
      if (tracked) {
        const after = await this.join(socket, doc.id, { history: false });
        if (revising) {
          let expected = joined.content;
          for (const e of [...plan].reverse()) expected = expected.slice(0, e.pos) + e.new + expected.slice(e.pos + e.old.length);
          const strayDelete = sharejsChanges(after.ranges).find((c) => c.kind === 'delete' && !deletes.some((d) => d.id === c.id));
          if (after.content !== expected || strayDelete) {
            throw new Error('Overleaf did not update the suggestion in place: the earlier suggested text may now be shown as a tracked deletion next to the new text. Look at the Review panel and reject that stray change; nothing else was written');
          }
          return { path: wanted, tracked, revised: true, applied: true };
        }
        const mine = sharejsChanges(after.ranges).filter((c) => c.id.startsWith(seed));
        if (mine.length === 0) {
          throw new Error('Overleaf took the edit but did not record it as a tracked change; it may have been applied as a plain edit. Check the document history in Overleaf');
        }
        return { path: wanted, tracked, applied: true, changes: mine.map(({ id, kind, position, text }) => ({ id, kind, position, text })) };
      }
      return { path: wanted, tracked, applied: true };
    } finally { await socket.close(); }
  }
}
