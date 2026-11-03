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

export class OverleafClient {
  constructor({ baseUrl, jar, csrf }) { this.baseUrl = baseUrl; this.jar = jar; this.csrf = csrf; }

  static async connect({ baseUrl, sessionCookie, cookieName = 'overleaf_session2' }) {
    if (!sessionCookie) throw new Error('no Overleaf session cookie: run "olmcp auth --cookie <value>" or set OVERLEAF_SESSION');
    const jar = new Jar({ [cookieName]: sessionCookie });
    const res = await request(jar, `${baseUrl}/project`);
    if (!res.ok) throw new Error(`Overleaf answered HTTP ${res.status} (is the session cookie current?)`);
    if (/name=["']loginForm["']|name=["']password["']/.test(res.text)) throw new Error('the session cookie has expired: run "olmcp auth --cookie <value>" again');
    const csrf = csrfFrom(res.text);
    if (!csrf) throw new Error('could not find the CSRF token (session expired, or Overleaf changed its page)');
    return new OverleafClient({ baseUrl, jar, csrf });
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

  /** The stored text of one document. Text with a pending tracked deletion is still present in it. */
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

  async reply(projectId, threadId, content) {
    const res = await request(this.jar, `${this.baseUrl}/project/${projectId}/thread/${threadId}/messages`, {
      method: 'POST', headers: this.headers(true), body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`could not post the reply: HTTP ${res.status}`);
    try { return JSON.parse(res.text); } catch { return null; }
  }

  /**
   * Edit a document as tracked changes ("Reviewing" mode): each edit becomes a tracked deletion of `old` and a
   * tracked insertion of `new`, which the researcher accepts or rejects in Overleaf. Refuses an edit whose `old`
   * text is not found exactly once, or touches text that already carries a tracked change.
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
      const plan = edits.map((e, n) => {
        if (typeof e.old !== 'string' || typeof e.new !== 'string' || !e.old) throw new Error(`edit ${n + 1}: "old" and "new" must be strings and "old" must not be empty`);
        const first = joined.content.indexOf(e.old);
        if (first < 0) throw new Error(`edit ${n + 1}: the old text was not found in ${wanted}`);
        if (joined.content.indexOf(e.old, first + 1) >= 0) throw new Error(`edit ${n + 1}: the old text appears more than once in ${wanted}; include more context`);
        const end = first + e.old.length;
        const clash = pending.find((c) => c.position < end && c.position + (c.kind === 'delete' ? c.text.length : c.text.length) > first);
        if (clash) throw new Error(`edit ${n + 1}: that text already carries a tracked change (${clash.kind}); resolve it in Overleaf first`);
        return { pos: first, old: e.old, new: e.new };
      });
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
      const seed = randomBytes(9).toString('hex'); // 18 hex characters; the server appends a counter
      const update = { doc: doc.id, op: ops, v: joined.version, ...(tracked ? { meta: { tc: seed } } : {}) };
      if (dryRun) return { path: wanted, tracked, ops, applied: false };
      await socket.rpc('applyOtUpdate', [doc.id, update]);
      if (tracked) {
        const after = await this.join(socket, doc.id, { history: false });
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
