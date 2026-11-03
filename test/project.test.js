import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { resolveProject } from '../src/project.js';

const ID = 'a'.repeat(24);

test('finds .olmcp.json in a parent folder', () => {
  const root = mkdtempSync(join(tmpdir(), 'olmcp-'));
  mkdirSync(join(root, 'sub'));
  writeFileSync(join(root, '.olmcp.json'), JSON.stringify({ project: ID, mode: 'direct' }));
  assert.deepEqual(resolveProject({ cwd: join(root, 'sub') }), { project: ID, mode: 'direct', commentTags: true });
});

test('still reads the pre-0.4 file name', () => {
  const root = mkdtempSync(join(tmpdir(), 'olmcp-'));
  writeFileSync(join(root, '.olmcp-overleaf.json'), JSON.stringify({ project: ID }));
  assert.equal(resolveProject({ cwd: root }).project, ID);
});

test('no project is a clear error', () => {
  const root = mkdtempSync(join(tmpdir(), 'olmcp-'));
  const saved = process.env.OVERLEAF_PROJECT; delete process.env.OVERLEAF_PROJECT;
  try { assert.throws(() => resolveProject({ cwd: root }), /olmcp init/); } finally { if (saved) process.env.OVERLEAF_PROJECT = saved; }
});
