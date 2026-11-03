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
