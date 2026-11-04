// Optional hashtags in comments: #agent (focus), #no-agent (hands off), #review / #suggest / #direct (mode).
// `#suggest` is an alias of `#review`: both hold the edit for the researcher in Overleaf's Review panel.
const HASH = /(?<![\w#/&=?.-])#(no-?agent|agent|suggest|review|direct)(?![\w-])/gi;

export function parseTags(text, enabled = true) {
  if (!enabled || !text) return { agent: null, mode: null };
  const found = new Set([...text.matchAll(HASH)].map((m) => m[1].toLowerCase().replace('-', '')));
  const agent = found.has('noagent') ? false : found.has('agent') ? true : null;
  const mode = found.has('suggest') || found.has('review') ? 'review' : found.has('direct') ? 'direct' : null;
  return { agent, mode };
}

export const stripTags = (text) => (text || '').replace(HASH, '').replace(/\s+/g, ' ').trim();

/** {id: reason}: "no-agent" always; "focus" for open untagged comments while any open comment is #agent. */
export function skipReasons(items) {
  const focus = items.some((c) => c.status === 'open' && c.agent === true);
  const out = {};
  for (const c of items) {
    if (c.agent === false) out[c.id] = 'no-agent';
    else if (focus && c.status === 'open' && c.agent !== true) out[c.id] = 'focus';
  }
  return out;
}
