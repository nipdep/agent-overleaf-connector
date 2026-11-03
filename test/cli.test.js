import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { sampleDocs, sampleThreads, startFake } from './fake-overleaf.js';

const cli = fileURLToPath(new URL('../src/cli.js', import.meta.url));
let fake;
before(async () => { fake = await startFake({ docs: sampleDocs(), threads: sampleThreads() }); });
after(() => fake.close());

const run = (args, input) => {
  return new Promise((resolve) => {
    import('node:child_process').then(({ spawn }) => {
      const child = spawn(process.execPath, [cli, ...args], { env: { ...process.env, OVERLEAF_BASE_URL: fake.url, OVERLEAF_SESSION: 'good', OLMCP_OVERLEAF_CONFIG: '/nonexistent/c.json' } });
      let out = ''; let err = '';
      child.stdout.on('data', (d) => { out += d; }); child.stderr.on('data', (d) => { err += d; });
      child.on('close', (code) => resolve({ code, out, err }));
      if (input) child.stdin.end(input); else child.stdin.end();
    });
  });
};

test('comments list --json has the shape the Python tool reads', async () => {
  const r = await run(['comments', 'list', 'p1', '--status', 'all', '--json']);
  assert.equal(r.code, 0, r.err);
  const [c] = JSON.parse(r.out);
  assert.deepEqual(Object.keys(c).sort(), ['column', 'docId', 'line', 'messages', 'path', 'position', 'resolved', 'selectedText', 'threadId']);
});

test('comments reply takes olcli-style arguments', async () => {
  const r = await run(['comments', 'reply', 'T1', '[agent] hi', 'p1', '--json']);
  assert.equal(r.code, 0, r.err);
  assert.equal(fake.state.posted.at(-1).content, '[agent] hi');
});

test('resolve, reopen and delete do not exist', async () => {
  for (const verb of ['resolve', 'reopen', 'delete']) {
    const r = await run(['comments', verb, 'T1', 'p1']);
    assert.equal(r.code, 1);
    assert.match(r.err, /left to the researcher/);
  }
  assert.equal(fake.state.resolveCalls, 0);
});

test('edit --stdin makes tracked changes', async () => {
  const r = await run(['edit', 'p1', 'main.tex', '--stdin', '--json'], JSON.stringify({ edits: [{ old: 'Intro line', new: 'Opening line' }] }));
  assert.equal(r.code, 0, r.err);
  assert.equal(JSON.parse(r.out).tracked, true);
});

test('pdf saves the compiled file', async () => {
  const { mkdtempSync, readFileSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join } = await import('node:path');
  const out = join(mkdtempSync(join(tmpdir(), 'ovpdf-')), 'paper.pdf');
  const r = await run(['pdf', 'p1', '-o', out]);
  assert.equal(r.code, 0, r.err);
  assert.equal(readFileSync(out, 'utf-8'), '%PDF-1.5 fake');
});

test('doctor reports the cookie, project and comment access', async () => {
  const r = await run(['doctor', '--project', 'p1']);
  assert.equal(r.code, 0, r.err + r.out);
  assert.match(r.out, /\[ok\] session cookie present/);
  assert.match(r.out, /\[ok\] Overleaf reachable, 1 comment thread\(s\) readable/);
});
