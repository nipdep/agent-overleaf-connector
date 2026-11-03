// Turning what Overleaf sends for a document into comments and tracked changes.

export const decodeUtf8 = (s) => Buffer.from(s, 'binary').toString('utf-8');

export function normalizeJoined(docId, args) {
  const [lines, version, , ranges, type = 'sharejs-text-ot'] = args;
  if (type === 'history-ot') {
    const content = typeof lines?.content === 'string' ? lines.content : '';
    return { docId, content, version, ranges: lines, type };
  }
  const decoded = Array.isArray(lines) ? lines.map(decodeUtf8) : [];
  const r = ranges || {};
  for (const c of r.comments || []) if (typeof c?.op?.c === 'string') c.op.c = decodeUtf8(c.op.c);
  for (const c of r.changes || []) {
    if (typeof c?.op?.i === 'string') c.op.i = decodeUtf8(c.op.i);
    if (typeof c?.op?.d === 'string') c.op.d = decodeUtf8(c.op.d);
  }
  return { docId, content: decoded.join('\n'), version, ranges: r, type };
}

export function collectDocs(project) {
  const docs = [];
  const walk = (folder, prefix) => {
    for (const d of folder.docs || []) docs.push({ id: d._id, path: prefix ? `${prefix}/${d.name}` : d.name });
    for (const f of folder.folders || []) walk(f, prefix ? `${prefix}/${f.name}` : f.name);
  };
  for (const f of project.rootFolder || []) walk(f, '');
  return docs;
}

export function lineColumn(content, pos) {
  const lines = content.slice(0, pos).split('\n');
  return { line: lines.length, column: lines[lines.length - 1].length + 1 };
}

export function commentsFromDocs(docs, joined, threads, status) {
  const out = [];
  docs.forEach((doc, i) => {
    const j = joined[i];
    if (j.type === 'history-ot') {
      for (const c of j.ranges.comments || []) {
        const first = (c.ranges || [])[0];
        if (!first) continue;
        const selectedText = c.ranges.map((r) => j.content.slice(r.pos, r.pos + r.length)).join('');
        const th = threads[c.id] || { messages: [] };
        out.push({ threadId: c.id, docId: doc.id, path: doc.path, position: first.pos, ...lineColumn(j.content, first.pos),
          selectedText, resolved: Boolean(c.resolved || th.resolved), messages: th.messages || [] });
      }
      return;
    }
    for (const c of j.ranges.comments || []) {
      const op = c.op || {};
      const threadId = op.t || c.id;
      if (!threadId || typeof op.p !== 'number') continue;
      const th = threads[threadId] || { messages: [] };
      out.push({ threadId, docId: doc.id, path: doc.path, position: op.p, ...lineColumn(j.content, op.p),
        selectedText: typeof op.c === 'string' ? op.c : '', resolved: Boolean(c.resolved || op.resolved || th.resolved),
        messages: th.messages || [] });
    }
  });
  return out
    .filter((c) => status === 'all' || (status === 'resolved' ? c.resolved : !c.resolved))
    .sort((a, b) => a.path.localeCompare(b.path) || a.position - b.position);
}

/** Tracked changes of a legacy (sharejs) document. */
export function sharejsChanges(ranges) {
  const out = [];
  for (const c of ranges?.changes ?? []) {
    const op = c?.op;
    if (typeof c?.id !== 'string' || !op || typeof op.p !== 'number') continue;
    if (typeof op.i === 'string') out.push({ id: c.id, kind: 'insert', position: op.p, text: op.i, userId: c.metadata?.user_id ?? null });
    else if (typeof op.d === 'string') out.push({ id: c.id, kind: 'delete', position: op.p, text: op.d, userId: c.metadata?.user_id ?? null });
  }
  return out;
}
