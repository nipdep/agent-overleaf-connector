// Which Overleaf project? --project, OVERLEAF_PROJECT, .olmcp.json (found upwards), or the git remote.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

export const PROJECT_FILE = '.olmcp.json';
const LEGACY_PROJECT_FILE = '.olmcp-overleaf.json'; // the name before 0.4.0
const ID = /(?<![0-9a-f])[0-9a-f]{24}(?![0-9a-f])/g;

/** The 24-character project id from an id, a project URL (.../project/<id>) or a git URL (.../<id>). */
export function parseProjectRef(ref) {
  const ids = String(ref ?? '').match(ID);
  if (!ids) throw new Error(`"${ref}" does not contain an Overleaf project id (24 hex characters; it is in the project's URL)`);
  return ids[ids.length - 1];
}

export function findProjectFile(cwd) {
  for (let dir = resolve(cwd); ; dir = dirname(dir)) {
    for (const name of [PROJECT_FILE, LEGACY_PROJECT_FILE]) {
      const f = join(dir, name);
      if (existsSync(f)) return f;
    }
    if (dirname(dir) === dir) return null;
  }
}

/**
 * Settings for this folder. `project` is null when none is configured: the MCP server then needs the agent to
 * pass one with each call. With `required`, a missing project is an error.
 */
export function resolveProject({ flag, cwd = process.cwd(), required = true } = {}) {
  let settings = {};
  const file = findProjectFile(cwd);
  if (file) { try { settings = JSON.parse(readFileSync(file, 'utf-8')); } catch { /* ignore a broken file */ } }
  let project = flag || process.env.OVERLEAF_PROJECT || settings.project || null;
  if (project) project = parseProjectRef(project);
  if (!project) {
    try {
      const url = execFileSync('git', ['remote', 'get-url', 'origin'], { cwd, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      if (/overleaf/i.test(url.replace(/^[a-z]+:\/\/[^@/]*@/i, '').split(/[/:]/)[0] || url)) project = (url.match(ID) || []).pop() || null;
    } catch { /* not a git repo */ }
  }
  if (!project && required) throw new Error('no Overleaf project: run "olmcp init <project-id>" in this folder, or set OVERLEAF_PROJECT, or pass --project');
  const mode = process.env.OLMCP_MODE || settings.mode || 'review';
  if (!['review', 'direct', 'suggest'].includes(mode)) throw new Error(`mode must be review or direct, got ${mode}`);
  return { project, mode: mode === 'suggest' ? 'review' : mode, commentTags: settings.commentTags !== false };
}
