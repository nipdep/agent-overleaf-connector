// Minimal cookie-carrying HTTP helper on top of Node's fetch. Redirects are followed by hand so cookies set
// along the way are kept.

export class Jar {
  constructor(initial = {}) { this.cookies = { ...initial }; }
  header() { return Object.entries(this.cookies).map(([k, v]) => `${k}=${v}`).join('; '); }
  absorb(headers) {
    const list = typeof headers.getSetCookie === 'function' ? headers.getSetCookie() : [];
    for (const line of list) {
      const m = /^([^=]+)=([^;]*)/.exec(line);
      if (m) this.cookies[m[1]] = m[2];
    }
  }
}

export async function request(jar, url, { method = 'GET', headers = {}, body, timeoutMs = 15000, maxRedirects = 5 } = {}) {
  let current = url;
  for (let hop = 0; ; hop++) {
    const res = await fetch(current, {
      method, body, redirect: 'manual', signal: AbortSignal.timeout(timeoutMs),
      headers: { Cookie: jar.header(), 'User-Agent': 'olmcp', ...headers },
    });
    jar.absorb(res.headers);
    const location = res.headers.get('location');
    if (res.status >= 300 && res.status < 400 && location && hop < maxRedirects) {
      current = new URL(location, current).toString();
      method = method === 'POST' && res.status !== 307 && res.status !== 308 ? 'GET' : method;
      if (method === 'GET') body = undefined;
      continue;
    }
    const buf = Buffer.from(await res.arrayBuffer());
    return { status: res.status, ok: res.ok, headers: res.headers, buffer: buf, text: buf.toString('utf-8') };
  }
}
