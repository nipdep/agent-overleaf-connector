import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { OverleafClient } from '../src/client.js';
import { decodePayload } from '../src/socketio.js';
import { sampleDocs, sampleThreads, startFake } from './fake-overleaf.js';

let fake; let client;
before(async () => {
  fake = await startFake({ docs: sampleDocs(), threads: sampleThreads() });
  client = await OverleafClient.connect({ baseUrl: fake.url, sessionCookie: 'good' });
});
after(() => fake.close());

test('decodes framed socket payloads', () => {
  assert.deepEqual(decodePayload('�3�2::�5�1::ab'), ['2::', '1::ab']);
  assert.deepEqual(decodePayload('2::'), ['2::']);
});

test('a bad cookie is reported as expired', async () => {
  await assert.rejects(OverleafClient.connect({ baseUrl: fake.url, sessionCookie: 'bad' }), /expired/);
});

test('lists comments with selected text, location and the thread messages', async () => {
  const [c] = await client.listComments('p1', { status: 'open' });
  assert.equal(c.threadId, 'T1');
  assert.equal(c.path, 'main.tex');
  assert.equal(c.selectedText, 'always outperforms the baselines');
  assert.deepEqual([c.line, c.column], [2, 12]);
  assert.equal(c.messages[0].content, 'shorten this #suggest');
  assert.equal((await client.listComments('p1', { status: 'resolved' })).length, 0);
});

test('reads documents in subfolders and decodes UTF-8', async () => {
  const sock = await client.openSocket('p1');
  const doc = await client.join(sock, 'd2');
  await sock.close();
  assert.match(doc.content, /Café results: ünïcode/);
});

test('posts a reply with the CSRF token', async () => {
  await client.reply('p1', 'T1', '[agent] done');
  assert.deepEqual(fake.state.posted.at(-1), { thread: 'T1', content: '[agent] done', csrf: 'csrf-1' });
});

test('there is no way to resolve a thread', async () => {
  assert.equal(typeof client.resolve, 'undefined');
  assert.equal(fake.state.resolveCalls, 0);
});

test('a tracked edit becomes a tracked delete plus insert; the stored text has the suggestion in and the deleted text out', async () => {
  const result = await client.editDocument('p1', 'main.tex', [{ old: 'always outperforms', new: 'outperforms' }]);
  assert.equal(result.applied, true);
  assert.deepEqual(result.changes.map((c) => c.kind).sort(), ['delete', 'insert']);
  assert.ok(fake.state.tcSeen.length === 1 && /^[0-9a-f]{18}$/.test(fake.state.tcSeen[0]));
  const ins = result.changes.find((c) => c.kind === 'insert');
  assert.equal(ins.text, 'outperforms');
  assert.equal(ins.position, 22);
  assert.match(fake.state.docs.d1.content, /^Intro line\nOur method outperforms the baselines/);
  const listed = await client.listChanges('p1');
  assert.equal(listed.length, 2);
});

test('an edit that starts outside a pending suggestion and runs into it is refused', async () => {
  await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'method outperforms', new: 'x' }]), /overlaps a tracked change/);
});

test('revising the temporary text of a pending suggestion changes it in place, with nothing accepted or rejected', async () => {
  const before = fake.state.docs.d1.ranges.changes.map((c) => ({ ...c, op: { ...c.op } }));
  const dry = await client.editDocument('p1', 'main.tex', [{ old: 'outperforms', new: 'beats' }], { dryRun: true });
  assert.deepEqual([dry.revising, dry.applied], [true, false]);
  const r = await client.editDocument('p1', 'main.tex', [{ old: 'outperforms', new: 'beats' }]);
  assert.deepEqual([r.revised, r.applied], [true, true]);
  const changes = fake.state.docs.d1.ranges.changes;
  assert.equal(changes.length, 2, 'still one deletion and one insertion');
  assert.equal(changes.find((c) => c.op.d).op.d, 'always outperforms', 'the original text is still the pending deletion');
  assert.equal(changes.find((c) => c.op.i).op.i, 'beats');
  assert.equal(changes.find((c) => c.op.d).id, before.find((c) => c.op.d).id);
  assert.match(fake.state.docs.d1.content, /^Intro line\nOur method beats the baselines/);
  // and again: a longer revision inside the same suggestion
  await client.editDocument('p1', 'main.tex', [{ old: 'beats', new: 'consistently beats' }]);
  assert.equal(fake.state.docs.d1.ranges.changes.find((c) => c.op.i).op.i, 'consistently beats');
});

test('a revision cannot be mixed with a new edit in one call', async () => {
  await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'beats', new: 'wins' }, { old: 'End', new: 'Finish' }]), /cannot both revise/);
});

test('a direct edit inside a pending suggestion is refused', async () => {
  await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'consistently beats', new: 'x' }], { tracked: false }), /pending tracked insertion/);
});

test("a suggestion by someone else is not revised in place", async () => {
  const other = fake.state.docs.d1.ranges.changes.find((c) => c.op.i);
  other.metadata.user_id = 'someone-else';
  try {
    await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'consistently beats', new: 'x' }]), /not provably yours/);
  } finally { other.metadata.user_id = 'u1'; }
});

test('if the server leaves the old suggestion as a tracked deletion, the revision says so', async () => {
  fake.state.ownInsertMode = 'strike';
  try {
    await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'consistently beats', new: 'wins' }]), /did not update the suggestion in place/);
  } finally {
    fake.state.ownInsertMode = undefined;
    fake.state.docs.d1.ranges.changes = fake.state.docs.d1.ranges.changes.filter((c) => !(c.op.d && c.op.d === 'consistently beats'));
  }
});

test('direct edit applies plain operations without a tracking id', async () => {
  const before = fake.state.tcSeen.length;
  await client.editDocument('p1', 'sections/results.tex', [{ old: 'text here', new: 'words' }], { tracked: false });
  assert.equal(fake.state.tcSeen.length, before);
  assert.match(fake.state.docs.d2.content, /ünïcode words\./);
});

test('refuses missing and ambiguous old text and unknown files without writing', async () => {
  const v = fake.state.docs.d1.version;
  await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'nope nope', new: 'x' }]), /not found/);
  await assert.rejects(client.editDocument('p1', 'main.tex', [{ old: 'e', new: 'x' }]), /more than once/);
  await assert.rejects(client.editDocument('p1', 'ghost.tex', [{ old: 'a', new: 'b' }]), /no document/);
  assert.equal(fake.state.docs.d1.version, v);
});

test('dry run sends nothing', async () => {
  const v = fake.state.docs.d1.version;
  const r = await client.editDocument('p1', 'main.tex', [{ old: 'Intro line', new: 'Opening line' }], { dryRun: true });
  assert.equal(r.applied, false);
  assert.equal(fake.state.docs.d1.version, v);
});

test('says so when the server did not record the edit as tracked', async () => {
  const f = await startFake({ docs: sampleDocs(), threads: {}, trackServerSupport: false });
  try {
    const c = await OverleafClient.connect({ baseUrl: f.url, sessionCookie: 'good' });
    await assert.rejects(c.editDocument('p1', 'main.tex', [{ old: 'Intro line', new: 'Opening' }]), /did not record it as a tracked change/);
  } finally { await f.close(); }
});

test('compiles with the project compiler and downloads the PDF with the server id', async () => {
  const { pdf } = await client.renderPdf('p1');
  assert.equal(pdf.toString(), '%PDF-1.5 fake');
  assert.equal(fake.state.pdfQuery, '?clsiserverid=cls-1');
});

test('a failed compile reports the TeX error lines', async () => {
  fake.state.compileFails = true;
  try {
    await assert.rejects(client.renderPdf('p1'), /did not succeed \(error\):\n! Undefined control sequence/);
  } finally { fake.state.compileFails = false; }
});
