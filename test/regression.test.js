// Regression suite for the alpha: the packaged program end to end, secret hygiene, the stable tool surface,
// documentation that matches the CLI, and a project with many documents.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { OverleafClient } from '../src/client.js';
import { TOOLS } from '../src/mcp.js';
import { Tools } from '../src/tools.js';
import { sampleDocs, sampleThreads, startFake } from './fake-overleaf.js';

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)));
const SECRET = 'SECRET-COOKIE-VALUE-0123456789';
const PID = 'c'.repeat(24);
let fake; let home; let prefix; let bin;

const run = (args, { input, env = {}, cwd = home } = {}) => new Promise((done) => {
  const child = spawn(bin, args, { cwd, env: { ...process.env, HOME: home, OVERLEAF_BASE_URL: fake.url, OVERLEAF_SESSION: '', OLMCP_OVERLEAF_CONFIG: '', ...env } });
  let out = ''; let err = '';
  child.stdout.on('data', (d) => { out += d; }); child.stderr.on('data', (d) => { err += d; });
  child.on('close', (code) => done({ code, out, err }));
  child.stdin.end(input ?? '');
});

before(async () => {
  fake = await startFake({ docs: sampleDocs(), threads: sampleThreads() });
  home = mkdtempSync(join(tmpdir(), 'olmcp-home-'));
  prefix = mkdtempSync(join(tmpdir(), 'olmcp-prefix-'));
  const pack = execFileSync('npm', ['pack', '--silent', '--pack-destination', prefix], { cwd: ROOT, encoding: 'utf-8' }).trim().split('\n').pop();
  execFileSync('npm', ['install', '-g', '--prefix', prefix, join(prefix, pack)], { stdio: 'ignore' });
  bin = join(prefix, 'bin', 'olmcp');
});
after(() => fake.close());

test('the packed program installs and both command names run', async () => {
  assert.ok(existsSync(bin) && existsSync(join(prefix, 'bin', 'olmcp-overleaf')));
  const r = await run(['help']);
  assert.equal(r.code, 0);
  assert.match(r.out, /^olmcp <command>/);
  for (const c of ['auth', 'comments list', 'comments reply', 'changes list', 'edit', 'pdf', 'check', 'doctor', 'init', 'mcp', 'list', 'show', 'address']) assert.ok(r.out.includes(c), `help lists ${c}`);
});

test('the version has one source and the commands report it', async () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf-8')).version;
  assert.equal((await run(['--version'])).out.trim(), pkg);
  assert.equal((await run(['version'])).out.trim(), pkg);
  assert.match(pkg, /^\d+\.\d+\.\d+(-[a-z]+\.\d+)?$/);
});

test('the package contains only what it needs', () => {
  const files = JSON.parse(execFileSync('npm', ['pack', '--dry-run', '--json'], { cwd: ROOT, encoding: 'utf-8' }))[0].files.map((f) => f.path);
  assert.ok(files.includes('src/cli.js') && files.includes('LICENSE') && files.includes('THIRD_PARTY_NOTICES.md'));
  assert.ok(!files.some((f) => f.startsWith('test/') || f.startsWith('docs/') || f.startsWith('.github/')), files.join(','));
});

test('end to end from a clean home: auth, doctor, init, list, address, pdf', async () => {
  let r = await run(['auth', '--cookie', 'good', '--base-url', fake.url]);
  assert.equal(r.code, 0, r.err);
  assert.equal((statSync(join(home, '.config', 'olmcp', 'config.json')).mode & 0o777).toString(8), '600');
  r = await run(['doctor', '--project', PID], { env: { OVERLEAF_SESSION: '' } });
  assert.equal(r.code, 0, r.out + r.err);
  r = await run(['init', PID, '--mode', 'review']);
  assert.equal(r.code, 0, r.err);
  assert.ok(existsSync(join(home, '.olmcp.json')) && existsSync(join(home, 'AGENTS.md')));
  assert.match(readFileSync(join(home, 'AGENTS.md'), 'utf-8'), /Never resolve/);
  r = await run(['list']);
  assert.equal(r.code, 0, r.err);
  const [c] = JSON.parse(r.out);
  assert.equal(c.id, 'T1');
  r = await run(['address', 'T1'], { input: JSON.stringify({ edits: [{ file: 'main.tex', old: 'always outperforms', new: 'outperforms' }], reply: 'Softened.' }) });
  assert.equal(r.code, 0, r.err);
  assert.equal(JSON.parse(r.out).mode, 'review');
  r = await run(['pdf', PID, '-o', join(home, 'p.pdf')]);
  assert.equal(r.code, 0, r.err);
  assert.equal(readFileSync(join(home, 'p.pdf'), 'utf-8'), '%PDF-1.5 fake');
});

test('the session cookie never appears in any output, and a bad cookie fails with a clear message', async () => {
  const outputs = [];
  outputs.push(await run(['auth', '--cookie', SECRET, '--base-url', fake.url]));
  outputs.push(await run(['doctor', '--project', PID]));
  outputs.push(await run(['check', PID]));
  outputs.push(await run(['list', '--project', PID]));
  outputs.push(await run(['comments', 'list', PID, '--json']));
  for (const o of outputs) { assert.ok(!o.out.includes(SECRET) && !o.err.includes(SECRET), `${o.out}${o.err}`); }
  const failed = outputs[2];
  assert.equal(failed.code, 1);
  assert.match(failed.err, /expired|forbidden|HTTP/i);
  await run(['auth', '--cookie', 'good', '--base-url', fake.url]);
});

test('there is no way to resolve, reopen or delete, in the CLI or the tool list', async () => {
  for (const verb of ['resolve', 'reopen', 'delete']) assert.equal((await run(['comments', verb, 'T1', PID])).code, 1);
  assert.ok(!TOOLS.some((t) => /resolve|reopen|delete|close/.test(t.name)));
  assert.ok(!OverleafClient.prototype.resolve && !OverleafClient.prototype.reopen && !OverleafClient.prototype.deleteComment);
  const src = readdirSync(join(ROOT, 'src')).map((f) => readFileSync(join(ROOT, 'src', f), 'utf-8')).join('\n');
  assert.ok(!/\/resolve|\/reopen|method:\s*'DELETE'/.test(src), 'no source path can resolve, reopen or delete a thread');
});

test('the MCP tool surface is stable', () => {
  const surface = TOOLS.map((t) => [t.name, (t.inputSchema.required || []).join(',')]);
  assert.deepEqual(surface, [
    ['list_comments', ''], ['show_comment', 'comment_id'], ['list_files', ''], ['read_file', 'path'],
    ['address_comment', 'comment_id,edits,reply'], ['reply_to_comment', 'comment_id,text'], ['list_tracked_changes', ''], ['render_pdf', ''],
  ]);
  assert.ok(TOOLS.every((t) => t.inputSchema.properties.project), 'every tool takes project');
});

test('every command the docs tell you to run exists', async () => {
  const known = new Set(['auth', 'comments', 'changes', 'edit', 'pdf', 'check', 'doctor', 'init', 'mcp', 'list', 'show', 'address', 'help']);
  const texts = ['README.md', 'docs/setup.md', 'docs/usage.md', 'docs/agents.md', 'CONTRIBUTING.md'].map((f) => readFileSync(join(ROOT, f), 'utf-8'));
  const seen = new Set();
  for (const t of texts) {
    const code = [...t.matchAll(/```[\s\S]*?```|`[^`\n]+`/g)].map((m) => m[0]).join('\n');
    for (const m of code.matchAll(/(?:^|[\s`(])olmcp(?:-overleaf)? ([a-z][a-z-]*)/g)) seen.add(m[1]);
  }
  for (const cmd of seen) assert.ok(known.has(cmd), `docs mention "olmcp ${cmd}" which does not exist`);
  assert.ok(seen.size >= 5, [...seen].join());
  const claimed = [...texts.join('\n').matchAll(/npm install -g (github:[\w./#-]+)/g)].map((m) => m[1]);
  assert.ok(claimed.every((c) => c.startsWith('github:nipdep/agent-overleaf-connector')), claimed.join());
});

test('a project with many documents is read in full, and edits land in the right one', async () => {
  const docs = {}; const threads = {}; const comments = [];
  for (let i = 0; i < 24; i++) {
    const id = `d${i}`;
    docs[id] = { name: `f${i}.tex`, folder: i % 2 === 1, version: 1, content: `Doc ${i} \u{1F600} text to change ${i}.\n`, ranges: { comments: [], changes: [] } };
    comments.push({ id: `r${i}`, op: { c: 'text', p: docs[id].content.indexOf('text'), t: `T${i}` } });
    docs[id].ranges.comments = [comments[i]];
    threads[`T${i}`] = { messages: [{ id: `m${i}`, content: `fix ${i}`, user: { email: 'me@example.com' } }] };
  }
  const f = await startFake({ docs, threads });
  try {
    const client = await OverleafClient.connect({ baseUrl: f.url, sessionCookie: 'good' });
    const tools = new Tools(client, { project: PID, mode: 'review' });
    assert.equal((await tools.listComments({ status: 'all' })).length, 24);
    await tools.addressComment('T17', [{ file: 'sections/f17.tex', old: 'text to change 17', new: 'words 17' }], 'Done.');
    assert.equal(f.state.docs.d17.ranges.changes.length, 2);
    assert.ok(Object.entries(f.state.docs).every(([id, d]) => id === 'd17' || d.ranges.changes.length === 0));
    assert.match(f.state.docs.d17.content, /\u{1F600}/u);
  } finally { await f.close(); }
});

test('a tracked edit never silently becomes a plain edit', async () => {
  const f = await startFake({ docs: sampleDocs(), threads: sampleThreads(), trackServerSupport: false });
  try {
    const client = await OverleafClient.connect({ baseUrl: f.url, sessionCookie: 'good' });
    const tools = new Tools(client, { project: PID, mode: 'review' });
    await assert.rejects(tools.addressComment('T1', [{ file: 'main.tex', old: 'always outperforms', new: 'x' }], 'r'), /did not take the edit|did not record/);
    assert.equal(f.state.posted.length, 0, 'no reply is posted for an edit that was not tracked');
  } finally { await f.close(); }
});
