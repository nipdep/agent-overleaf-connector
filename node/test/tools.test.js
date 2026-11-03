import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { OverleafClient } from '../src/client.js';
import { parseTags, skipReasons, stripTags } from '../src/tags.js';
import { wordDiff } from '../src/textdiff.js';
import { Tools, ToolError } from '../src/tools.js';
import { startFake } from './fake-overleaf.js';

const docs = () => ({
  d1: { name: 'main.tex', folder: false, version: 3,
    content: 'Intro line\nOur method always outperforms the baselines on all tasks.\nSecond paragraph stays.\nThird idea here.\n',
    ranges: { comments: [
      { id: 'r1', op: { c: 'always outperforms the baselines', p: 22, t: 'T1' } },
      { id: 'r2', op: { c: 'Second paragraph stays.', p: 67, t: 'T2' } },
      { id: 'r3', op: { c: 'Third idea here.', p: 91, t: 'T3' } },
    ], changes: [] } },
});
const human = (id, content) => ({ id, content, user: { email: 'me@example.com' } });
const threads = () => ({
  T1: { messages: [human('m1', 'make this less absolute #review')] },
  T2: { messages: [human('m2', 'Alice, check this one #no-agent')] },
  T3: { messages: [human('m3', 'rephrase #direct')] },
});

let fake; let tools;
before(async () => {
  fake = await startFake({ docs: docs(), threads: threads() });
  const client = await OverleafClient.connect({ baseUrl: fake.url, sessionCookie: 'good' });
  tools = new Tools(client, { project: 'p1', mode: 'review' });
});
after(() => fake.close());

test('tags: parsing, conflicts and stripping', () => {
  assert.deepEqual(parseTags('we need to fix the wording in here to shorten this #agent #suggest'), { agent: true, mode: 'review' });
  assert.deepEqual(parseTags('#agent #no-agent'), { agent: false, mode: null });
  assert.deepEqual(parseTags('#direct #review'), { agent: null, mode: 'review' });
  assert.deepEqual(parseTags('see page.html#direct and a#agent'), { agent: null, mode: null });
  assert.deepEqual(parseTags('#agent', false), { agent: null, mode: null });
  assert.equal(stripTags('shorten this #agent #suggest please'), 'shorten this please');
});

test('focus and hands-off', () => {
  const items = [{ id: 'a', status: 'open', agent: true }, { id: 'b', status: 'open', agent: null }, { id: 'c', status: 'open', agent: false }, { id: 'd', status: 'addressed', agent: null }];
  assert.deepEqual(skipReasons(items), { b: 'focus', c: 'no-agent' });
});

test('word diff reads on one line', () => {
  assert.equal(wordDiff('Our method always outperforms the baselines', 'Our method outperforms most baselines'), 'Our method [-always-] outperforms [-the-]{+most+} baselines');
  assert.equal(wordDiff('same', 'same'), 'same');
});

test('list_comments hides #no-agent, derives the mode and the request', async () => {
  const list = await tools.listComments();
  assert.deepEqual(list.map((c) => c.id).sort(), ['T1', 'T3']);
  const t1 = list.find((c) => c.id === 't1'.toUpperCase());
  assert.equal(t1.request, 'make this less absolute');
  assert.deepEqual([t1.mode, t1.mode_chosen_by_researcher, t1.selected_text], ['review', true, 'always outperforms the baselines']);
  const all = await tools.listComments({ status: 'all', include_skipped: true });
  assert.ok(!all.some((c) => c.id === 'T2'), 'include_skipped never lifts #no-agent');
});

test('a #no-agent comment cannot be edited or replied to', async () => {
  await assert.rejects(tools.addressComment('T2', [{ file: 'main.tex', old: 'Second paragraph stays.', new: 'x' }], 'r'), /#no-agent/);
  await assert.rejects(tools.replyToComment('T2', 'hello'), /#no-agent/);
});

test("the researcher's tag beats the agent's mode argument", async () => {
  await assert.rejects(tools.addressComment('T1', [{ file: 'main.tex', old: 'always', new: 'x' }], 'r', 'direct'), /asked for 'review'/);
});

test('address_comment in review mode makes tracked changes and posts the reply with the diff', async () => {
  const out = await tools.addressComment('T1', [{ file: 'main.tex', old: 'always outperforms the baselines', new: 'outperforms most baselines' }], 'Softened the claim.');
  assert.equal(out.mode, 'review');
  const kinds = fake.state.docs.d1.ranges.changes.map((c) => Object.keys(c.op)[0]).sort();
  assert.deepEqual(kinds, ['d', 'i']);
  const last = fake.state.posted.at(-1);
  assert.equal(last.thread, 'T1');
  assert.match(last.content, /^\[agent\] Softened the claim\.\n\nTracked change in main\.tex:\n.*\[-always-\]/s);
  assert.match(last.content, /Review panel/);
  const [t1] = await tools.listComments({ status: 'addressed' });
  assert.equal(t1.status, 'addressed');
  assert.equal((await tools.listComments()).some((c) => c.id === 'T1'), false);
});

test('direct tag applies a plain edit', async () => {
  const before = fake.state.tcSeen.length;
  const out = await tools.addressComment('T3', [{ file: 'main.tex', old: 'Third idea here.', new: 'Third thought.' }], 'Rephrased.');
  assert.equal(out.mode, 'direct');
  assert.equal(fake.state.tcSeen.length, before);
  assert.match(fake.state.docs.d1.content, /Third thought\./);
  assert.doesNotMatch(fake.state.posted.at(-1).content, /Review panel/);
});

test('a failing edit changes nothing and posts nothing', async () => {
  fake.state.threads.T4 = { messages: [human('m4', 'x')] };
  fake.state.docs.d1.ranges.comments.push({ id: 'r4', op: { c: 'Intro line', p: 0, t: 'T4' } });
  const posted = fake.state.posted.length; const v = fake.state.docs.d1.version;
  await assert.rejects(tools.addressComment('T4', [{ file: 'main.tex', old: 'not in the document', new: 'x' }], 'r'), /did not take the edit/);
  assert.equal(fake.state.posted.length, posted);
  assert.equal(fake.state.docs.d1.version, v);
});

test('read_file, list_files, render_pdf', async () => {
  assert.deepEqual((await tools.listFiles()).files, ['main.tex']);
  const r = await tools.readFile('main.tex', { start_line: 1, end_line: 1 });
  assert.equal(r.content, 'Intro line');
});

// ---- the MCP server over stdio, speaking JSON-RPC like a client
function mcpSession() {
  const cli = fileURLToPath(new URL('../src/cli.js', import.meta.url));
  const child = spawn(process.execPath, [cli, 'mcp', '--project', 'p1'], { env: { ...process.env, OVERLEAF_BASE_URL: fake.url, OVERLEAF_SESSION: 'good', OLMCP_OVERLEAF_CONFIG: '/nonexistent/c.json' } });
  let buffer = ''; const waiting = new Map();
  child.stdout.on('data', (d) => {
    buffer += d;
    let i;
    while ((i = buffer.indexOf('\n')) >= 0) {
      const msg = JSON.parse(buffer.slice(0, i)); buffer = buffer.slice(i + 1);
      waiting.get(msg.id)?.(msg);
    }
  });
  let n = 0;
  const call = (method, params) => new Promise((resolve) => { const id = ++n; waiting.set(id, resolve); child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n'); });
  return { call, notify: (method) => child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method }) + '\n'), close: () => { child.stdin.end(); return new Promise((r) => child.on('close', r)); } };
}

test('MCP: initialize, list tools, call a tool, refuse #no-agent as an error result', async () => {
  const s = mcpSession();
  const init = await s.call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } });
  assert.equal(init.result.protocolVersion, '2025-06-18');
  s.notify('notifications/initialized');
  const list = await s.call('tools/list', {});
  assert.deepEqual(list.result.tools.map((t) => t.name), ['list_comments', 'show_comment', 'list_files', 'read_file', 'address_comment', 'reply_to_comment', 'list_tracked_changes', 'render_pdf']);
  assert.ok(!list.result.tools.some((t) => /resolve|reopen|delete/.test(t.name)));
  const files = await s.call('tools/call', { name: 'list_files', arguments: {} });
  assert.equal(files.result.isError, false);
  assert.match(files.result.content[0].text, /main\.tex/);
  const refused = await s.call('tools/call', { name: 'reply_to_comment', arguments: { comment_id: 'T2', text: 'hi' } });
  assert.equal(refused.result.isError, true);
  assert.match(refused.result.content[0].text, /#no-agent/);
  assert.equal((await s.call('nope', {})).error.code, -32601);
  await s.close();
});
