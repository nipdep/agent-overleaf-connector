// Which Overleaf project? --project, OVERLEAF_PROJECT, .olmcp-overleaf.json (found upwards), or the git remote.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

export const PROJECT_FILE = '.olmcp-overleaf.json';
const ID = /[0-9a-f]{24}/g;

export function findProjectFile(cwd) {
  for (let dir = resolve(cwd); ; dir = dirname(dir)) {
    const f = join(dir, PROJECT_FILE);
    if (existsSync(f)) return f;
    if (dirname(dir) === dir) return null;
  }
}

export function resolveProject({ flag, cwd = process.cwd() } = {}) {
  let settings = {};
  const file = findProjectFile(cwd);
  if (file) { try { settings = JSON.parse(readFileSync(file, 'utf-8')); } catch { /* ignore a broken file */ } }
  let project = flag || process.env.OVERLEAF_PROJECT || settings.project;
  if (!project) {
    try {
      const url = execFileSync('git', ['remote', 'get-url', 'origin'], { cwd, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      if (/overleaf/i.test(url.replace(/^[a-z]+:\/\/[^@/]*@/i, '').split(/[/:]/)[0] || url)) project = (url.match(ID) || []).pop();
    } catch { /* not a git repo */ }
  }
  if (!project) throw new Error(`no Overleaf project: run "olmcp-overleaf init <project-id>" in this folder, or set OVERLEAF_PROJECT, or pass --project`);
  const mode = process.env.OLMCP_MODE || settings.mode || 'review';
  if (!['review', 'direct', 'suggest'].includes(mode)) throw new Error(`mode must be review or direct, got ${mode}`);
  return { project, mode: mode === 'suggest' ? 'review' : mode, commentTags: settings.commentTags !== false };
}
