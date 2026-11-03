// An in-memory imitation of the parts of Overleaf this client talks to (cookie + CSRF page, the project
// socket over Socket.IO 0.9 long polling, thread endpoints). It encodes how the protocol is understood from
// olcli's source and Overleaf's behaviour; it cannot prove the real service agrees.
import { createServer } from 'node:http';

export function startFake({ docs, threads = {}, trackServerSupport = true }) {
  const state = {
    docs, threads, sockets: new Map(), posted: [], tcSeen: [], resolveCalls: 0, seq: 0, sid: 0, trackServerSupport,
  };
  const project = () => ({ rootFolder: [{ _id: 'root', docs: Object.entries(state.docs).filter(([, d]) => !d.folder).map(([id, d]) => ({ _id: id, name: d.name })),
    folders: [{ _id: 'f1', name: 'sections', docs: Object.entries(state.docs).filter(([, d]) => d.folder).map(([id, d]) => ({ _id: id, name: d.name })), folders: [] }] }] });
  const enc = (s) => Buffer.from(s, 'utf-8').toString('binary');
  const frame = (packets) => (packets.length === 1 ? packets[0] : packets.map((p) => `�${p.length}�${p}`).join(''));

  function applyUpdate(doc, update) {
    const tc = update.meta?.tc;
    for (const op of update.op) {
      if (op.i !== undefined) {
        doc.content = doc.content.slice(0, op.p) + op.i + doc.content.slice(op.p);
        if (tc && state.trackServerSupport) doc.ranges.changes.push({ id: `${tc}${String(++state.seq).padStart(6, '0')}`, op: { i: op.i, p: op.p }, metadata: { user_id: 'u1', ts: '2026-11-03T00:00:00Z' } });
      } else if (op.d !== undefined) {
        if (tc && state.trackServerSupport) doc.ranges.changes.push({ id: `${tc}${String(++state.seq).padStart(6, '0')}`, op: { d: op.d, p: op.p }, metadata: { user_id: 'u1', ts: '2026-11-03T00:00:00Z' } });
        else doc.content = doc.content.slice(0, op.p) + doc.content.slice(op.p + op.d.length);
      }
    }
    if (tc) state.tcSeen.push(tc);
    doc.version += 1;
  }

  function handleEvent(sock, id, { name, args }) {
    let ack;
    if (name === 'joinDoc') {
      const doc = state.docs[args[0]];
      ack = doc ? [null, doc.content.split('\n').map(enc), doc.version, [], doc.ranges, 'sharejs-text-ot'] : ['not found'];
    } else if (name === 'applyOtUpdate') {
      const doc = state.docs[args[0]];
      if (args[1].v !== doc.version) ack = [{ message: 'version mismatch' }];
      else { applyUpdate(doc, args[1]); ack = [null]; }
    } else ack = ['unknown event'];
    sock.queue.push(`6:::${id}+${JSON.stringify(ack)}`);
  }

  const server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', async () => {
      const body = Buffer.concat(chunks).toString('utf-8');
      const send = (code, text, type = 'text/plain') => { res.writeHead(code, { 'content-type': type }); res.end(text); };
      const authed = /overleaf_session2=good/.test(req.headers.cookie || '');
      if (url.pathname === '/project' && req.method === 'GET') {
        return authed ? send(200, '<html><meta name="ol-csrfToken" content="csrf-1"></html>', 'text/html')
          : send(200, '<form name="loginForm"></form>', 'text/html');
      }
      if (!authed) return send(403, 'no');
      if (url.pathname === '/socket.io/1/') return send(200, `sid${++state.sid}:60:60:xhr-polling`);
      const poll = /^\/socket\.io\/1\/xhr-polling\/(\w+)$/.exec(url.pathname);
      if (poll) {
        const sid = poll[1] + (url.searchParams.get('projectId') || '');
        let sock = state.sockets.get(sid);
        if (!sock) { sock = { queue: ['1::', `5:::${JSON.stringify({ name: 'joinProjectResponse', args: [{ project: project() }] })}`] }; state.sockets.set(sid, sock); }
        if (req.method === 'POST') {
          if (body.startsWith('0::')) { state.sockets.delete(sid); return send(200, '1'); }
          const m = /^5:(\d+)\+::(.*)$/s.exec(body);
          if (m) handleEvent(sock, Number(m[1]), JSON.parse(m[2]));
          return send(200, '1');
        }
        const out = sock.queue.splice(0);
        return send(200, out.length ? frame(out) : '8::');
      }
      if (url.pathname.endsWith('/threads')) return send(200, JSON.stringify(state.threads), 'application/json');
      const msg = /\/thread\/(\w+)\/messages$/.exec(url.pathname);
      if (msg && req.method === 'POST') {
        const content = JSON.parse(body).content;
        state.threads[msg[1]] ??= { messages: [] };
        state.threads[msg[1]].messages.push({ id: `m${state.posted.length + 100}`, content, user_id: 'u1' });
        state.posted.push({ thread: msg[1], content, csrf: req.headers['x-csrf-token'] });
        return send(200, JSON.stringify({ id: 'new', content }), 'application/json');
      }
      if (/\/resolve$/.test(url.pathname)) { state.resolveCalls += 1; return send(204, ''); }
      return send(404, 'nope');
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => {
    resolve({ state, url: `http://127.0.0.1:${server.address().port}`, close: () => new Promise((r) => { server.closeAllConnections?.(); server.close(r); }) });
  }));
}

export const sampleDocs = () => ({
  d1: { name: 'main.tex', folder: false, version: 3, content: 'Intro line\nOur method always outperforms the baselines on all tasks.\nEnd\n',
    ranges: { comments: [{ id: 'r1', op: { c: 'always outperforms the baselines', p: 22, t: 'T1' } }], changes: [] } },
  d2: { name: 'results.tex', folder: true, version: 1, content: 'Café results: ünïcode text here.\n', ranges: { comments: [], changes: [] } },
});
export const sampleThreads = () => ({ T1: { messages: [{ id: 'm1', content: 'shorten this #suggest', user: { email: 'me@example.com' } }], resolved: false } });
