// A Socket.IO 0.9 client over xhr-polling: just enough to join a project, join documents and send updates.
// Overleaf's editor speaks this protocol; there is no documented API for it.
import { request } from './http.js';

export function decodePayload(payload) {
  if (!payload) return [];
  if (!payload.startsWith('�')) return [payload];
  const packets = [];
  let i = 0;
  while (i < payload.length && payload[i] === '�') {
    i += 1;
    let len = '';
    while (i < payload.length && payload[i] !== '�') len += payload[i++];
    if (i >= payload.length) break;
    i += 1;
    const n = Number.parseInt(len, 10);
    if (!Number.isFinite(n) || n < 0) break;
    packets.push(payload.slice(i, i + n));
    i += n;
  }
  return packets;
}

export class SocketError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export class ProjectSocket {
  constructor(jar, baseUrl, projectId) {
    this.jar = jar; this.baseUrl = baseUrl; this.projectId = projectId;
    this.sid = null; this.project = null; this.acks = new Map(); this.closed = false; this.nextId = 1;
  }

  url() {
    return `${this.baseUrl}/socket.io/1/xhr-polling/${this.sid}?projectId=${encodeURIComponent(this.projectId)}&t=${Date.now()}`;
  }

  async open() {
    const res = await request(this.jar, `${this.baseUrl}/socket.io/1/?projectId=${encodeURIComponent(this.projectId)}&t=${Date.now()}`, { timeoutMs: 8000 });
    if (!res.ok) throw new SocketError(`could not open the project socket: HTTP ${res.status}`, res.status);
    this.sid = res.text.trim().split(':')[0];
    if (!this.sid) throw new SocketError('could not open the project socket: no session id');
    for (let attempt = 0; attempt < 8 && !this.project; attempt++) await this.poll();
    if (!this.project) throw new SocketError('the project socket never sent joinProjectResponse (not allowed, or Overleaf changed)');
    return this;
  }

  async post(packet) {
    const res = await request(this.jar, this.url(), {
      method: 'POST', body: packet, headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, timeoutMs: 8000,
    });
    if (!res.ok) throw new SocketError(`socket post failed: HTTP ${res.status}`, res.status);
  }

  async poll() {
    const res = await request(this.jar, this.url(), { timeoutMs: 20000 });
    if (!res.ok) throw new SocketError(`socket poll failed: HTTP ${res.status}`, res.status);
    for (const packet of decodePayload(res.text)) {
      if (packet.startsWith('2::')) { await this.post('2::'); continue; }
      if (packet.startsWith('0::')) { this.closed = true; throw new SocketError('the server closed the socket (is the session valid?)'); }
      if (packet.startsWith('5:::')) {
        try {
          const event = JSON.parse(packet.slice(4));
          if (event?.name === 'joinProjectResponse' && event.args?.[0]?.project) this.project = event.args[0].project;
        } catch { /* not an event we know */ }
        continue;
      }
      const ack = /^6:::(\d+)\+?(.*)$/s.exec(packet);
      if (ack) {
        let args = [];
        if (ack[2]) { const parsed = JSON.parse(ack[2]); args = Array.isArray(parsed) ? parsed : [parsed]; }
        this.acks.set(Number(ack[1]), args);
      }
    }
  }

  /** Send an event and wait for its acknowledgement; resolves to the ack arguments after the error slot. */
  async rpc(name, args) {
    const id = this.nextId++;
    await this.post(`5:${id}+::${JSON.stringify({ name, args })}`);
    for (let attempt = 0; attempt < 12; attempt++) {
      if (this.acks.has(id)) {
        const [error, ...rest] = this.acks.get(id);
        this.acks.delete(id);
        if (error) throw new SocketError(`${name} failed: ${typeof error === 'string' ? error : error.message || JSON.stringify(error)}`);
        return rest;
      }
      await this.poll();
    }
    throw new SocketError(`${name} was not acknowledged`);
  }

  async close() {
    if (this.closed || !this.sid) return;
    this.closed = true;
    try { await this.post('0::'); } catch { /* best effort */ }
  }
}
