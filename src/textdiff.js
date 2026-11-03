// Inline word diff for thread replies: `kept [-removed-]{+added+} kept`.
const TOKEN = /\s*(\\[A-Za-z]+|\w+(?:['’-]\w+)*|[^\w\s])/gy;

function tokens(text) {
  const out = [];
  TOKEN.lastIndex = 0;
  let m;
  while ((m = TOKEN.exec(text)) !== null) {
    out.push({ t: m[1], sp: m[0].length > m[1].length });
    if (TOKEN.lastIndex === m.index) TOKEN.lastIndex++;
  }
  return out;
}
const join = (toks) => toks.reduce((s, x) => s + (x.sp && s ? ' ' : '') + x.t, '');

/** Opcodes like difflib: [op, i1, i2, j1, j2] with adjacent changes merged into one replace. */
function opcodes(a, b) {
  const n = a.length; const m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const ops = []; let i = 0; let j = 0;
  const push = (op, i1, i2, j1, j2) => {
    const last = ops[ops.length - 1];
    if (op !== 'equal' && last && last[0] !== 'equal' && last[2] === i1 && last[4] === j1) { last[2] = i2; last[4] = j2; last[0] = 'replace'; return; }
    ops.push([op, i1, i2, j1, j2]);
  };
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { push('equal', i, i + 1, j, j + 1); i++; j++; }
    else if (j < m && (i === n || lcs[i][j + 1] >= lcs[i + 1][j])) { push('insert', i, i, j, j + 1); j++; }
    else { push('delete', i, i + 1, j, j); i++; }
  }
  // merge consecutive equals
  const merged = [];
  for (const o of ops) {
    const last = merged[merged.length - 1];
    if (o[0] === 'equal' && last && last[0] === 'equal') { last[2] = o[2]; last[4] = o[4]; } else merged.push([...o]);
  }
  return merged;
}

export function wordDiff(oldText, newText) {
  const a = tokens(oldText); const b = tokens(newText);
  const out = []; let afterPiece = false;
  const put = (piece, spaceBefore, glue = false, equalTok = '') => {
    const wordFollowsMarker = afterPiece && /^[A-Za-z0-9_\\]/.test(equalTok.slice(0, 1));
    if (out.length && (spaceBefore || wordFollowsMarker) && !glue) out.push(' ');
    out.push(piece);
    afterPiece = !equalTok;
  };
  for (const [op, i1, i2, j1, j2] of opcodes(a.map((x) => x.t), b.map((x) => x.t))) {
    if (op === 'equal') { for (const x of b.slice(j1, j2)) put(x.t, x.sp, false, x.t); continue; }
    if (i2 > i1) put(`[-${join(a.slice(i1, i2))}-]`, a[i1].sp);
    if (j2 > j1) put(`{+${join(b.slice(j1, j2))}+}`, b[j1].sp, i2 > i1);
  }
  return out.join('').trim();
}

const cut = (s, n, fromEnd) => {
  if (s.length <= n) return s;
  const piece = fromEnd ? s.slice(s.length - n) : s.slice(0, n);
  const snapped = fromEnd ? piece.replace(/^\S*\s/, '') : piece.replace(/\s\S*$/, '');
  return fromEnd ? `\u2026${snapped || piece}` : `${snapped || piece}\u2026`;
};

/**
 * The change as two short, plain readings of the same passage: what it said before and what it says now, cropped to
 * the words that changed plus a little context on each side. Easier to read than inline diff markup.
 */
export function beforeAfter(oldText, newText, { context = 70, limit = 360 } = {}) {
  const a = oldText.replace(/\s+/g, ' ').trim(); const b = newText.replace(/\s+/g, ' ').trim();
  let p = 0;
  while (p < a.length && p < b.length && a[p] === b[p]) p++;
  p = Math.max(a.lastIndexOf(' ', p - 1) + 1, 0); // start the changed part at a word boundary
  let s = 0;
  while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++;
  const tail = a.length - s;
  s = a.length - (tail < a.length && a[tail] !== ' ' ? (a.indexOf(' ', tail) === -1 ? a.length : a.indexOf(' ', tail)) : tail);
  const head = cut(a.slice(0, p), context, true); const rest = cut(a.slice(a.length - s), context, false);
  const mid = (t, from, to) => { const m = t.slice(from, t.length - to); return m.length > limit ? `${m.slice(0, limit / 2).trimEnd()} \u2026 ${m.slice(-limit / 2).trimStart()}` : m; };
  return { before: `${head}${mid(a, p, s)}${rest}`, after: `${head}${mid(b, p, s)}${rest}` };
}
