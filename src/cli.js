#!/usr/bin/env node
// olmcp: the command line and MCP server for Overleaf review comments, tracked-change edits and the PDF.
// (`olmcp-overleaf` is an alias of the same program.)
import { readFileSync, writeFileSync } from 'node:fs';
import { OverleafClient } from './client.js';
import { configPath, loadConfig, saveConfig } from './config.js';
import { existsSync, writeFileSync as write } from 'node:fs';
import { PROJECT_FILE, resolveProject } from './project.js';
import { Tools } from './tools.js';
import { serve } from './mcp.js';
import { AGENTS_MD } from './agents-md.js';
import { VERSION } from './version.js';

const USAGE = `olmcp <command>

  auth --cookie VALUE [--base-url URL] [--cookie-name NAME]   store the session cookie (mode 0600)
  comments list <project> [--status all|open|resolved] [--json]
  comments reply <thread> <text> <project> [--json]
  changes list <project> [--json]
  edit <project> <file> (--old TEXT --new TEXT | --stdin) [--direct] [--dry-run] [--json]
       --stdin reads {"edits":[{"old":"...","new":"..."}]}; edits are tracked changes unless --direct
  pdf <project> [-o FILE] [--draft]   compile with Overleaf's compiler and save the PDF (default output.pdf)
  create <project> <path> [--dry-run]       create a NEW text file with the content read from stdin (never overwrites)
  check <project>
  doctor [--project ID]                     check Node, the cookie, the project and comment access

  init <project-id> [--mode review|direct]   write .olmcp.json and AGENTS.md here, show how to add the MCP server
  mcp [--project ID]                        run the MCP server (stdio) for Claude Code, Codex, ...
  list [--status S] [--all] [--json]  |  show <id>  |  address <id> < edit.json   (same operations as the MCP tools)

There is no command to resolve, reopen or delete a comment thread.`;

function parse(argv) {
  const positional = []; const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      if (['json', 'stdin', 'direct', 'dry-run', 'changes', 'draft', 'all'].includes(key)) flags[key] = true;
      else if (key === 'version') flags.version = true;
      else flags[key] = argv[++i];
    } else if (a === '-o') flags.o = argv[++i];
    else positional.push(a);
  }
  return { positional, flags };
}

const print = (data, json, text) => console.log(json ? JSON.stringify(data, null, 2) : text(data));

async function main(argv) {
  const { positional: p, flags } = parse(argv);
  const cmd = p[0];
  if (cmd === '--version' || cmd === 'version' || flags.version) { console.log(VERSION); return 0; }
  if (!cmd || cmd === 'help' || flags.help) { console.log(USAGE); return 0; }
  if (cmd === 'auth') {
    if (!flags.cookie) throw new Error('usage: olmcp auth --cookie <value>');
    saveConfig({ sessionCookie: flags.cookie, ...(flags['base-url'] ? { baseUrl: flags['base-url'] } : {}),
      ...(flags['cookie-name'] ? { cookieName: flags['cookie-name'] } : {}) });
    console.log(`saved to ${configPath()}`);
    return 0;
  }
  if (cmd === 'comments' && ['resolve', 'reopen', 'delete'].includes(p[1])) {
    throw new Error(`"comments ${p[1]}" does not exist in olmcp: resolving, reopening and deleting threads is left to the researcher in Overleaf`);
  }
  if (cmd === 'doctor') {
    const line = (ok, text) => { console.log(`[${ok ? 'ok' : 'FAIL'}] ${text}`); return ok; };
    let good = line(Number(process.versions.node.split('.')[0]) >= 20, `Node ${process.versions.node} (20 or later needed)`);
    const cfg = loadConfig();
    good = line(Boolean(cfg.sessionCookie), `session cookie ${cfg.sessionCookie ? 'present' : 'missing: olmcp auth --cookie ...'} (${cfg.baseUrl})`) && good;
    let project = null;
    try { project = resolveProject({ flag: flags.project }); line(true, `project ${project.project}, default mode ${project.mode}`); }
    catch (e) { good = line(false, e.message) && good; }
    if (cfg.sessionCookie && project) {
      try {
        const n = (await (await OverleafClient.connect(cfg)).listComments(project.project, { status: 'all' })).length;
        line(true, `Overleaf reachable, ${n} comment thread(s) readable`);
      } catch (e) { good = line(false, e.message) && good; }
    }
    console.log('[info] this tool has no command to resolve, reopen or delete a thread; the cookie file is readable by anything running as you');
    return good ? 0 : 1;
  }
  if (cmd === 'init') {
    if (!p[1] || !/^[0-9a-f]{24}$/.test(p[1])) throw new Error('usage: init <24-character project id>');
    const mode = flags.mode || 'review';
    if (!['review', 'direct'].includes(mode)) throw new Error('mode must be review or direct');
    write(PROJECT_FILE, JSON.stringify({ project: p[1], mode }, null, 2) + '\n');
    if (!existsSync('AGENTS.md')) write('AGENTS.md', AGENTS_MD);
    console.log(`wrote ${PROJECT_FILE}${existsSync('AGENTS.md') ? ' and AGENTS.md (an existing AGENTS.md is left alone)' : ''}
Add the server to your agent (run from this folder):
  claude mcp add olmcp -- "$(which olmcp)" mcp
  codex mcp add olmcp -- "$(which olmcp)" mcp`);
    return 0;
  }
  const client = await OverleafClient.connect(loadConfig());
  if (['mcp', 'list', 'show', 'address'].includes(cmd)) {
    const settings = resolveProject({ flag: flags.project, required: cmd !== 'mcp' });
    const tools = new Tools(client, settings);
    if (cmd === 'mcp') { await serve(tools); return 0; }
    let result;
    if (cmd === 'list') result = await tools.listComments({ status: flags.status || 'open', include_skipped: !!flags.all });
    else if (cmd === 'show') result = await tools.showComment(p[1]);
    else {
      const body = JSON.parse(readFileSync(0, 'utf-8'));
      result = await tools.addressComment(p[1], body.edits, body.reply, body.mode);
    }
    console.log(JSON.stringify(result, null, 2));
    return 0;
  }
  if (cmd === 'comments' && p[1] === 'list') {
    const comments = await client.listComments(p[2], { status: flags.status || 'all' });
    print(comments, flags.json, (cs) => cs.map((c) => `${c.resolved ? '[resolved]' : '[open]'} ${c.threadId} ${c.path}:${c.line} "${c.selectedText.slice(0, 60)}"\n${c.messages.map((m) => `  - ${m.content}`).join('\n')}`).join('\n') || 'no comments');
    return 0;
  }
  if (cmd === 'comments' && p[1] === 'reply') {
    if (p.length < 5) throw new Error('usage: comments reply <thread> <text> <project>');
    const message = await client.reply(p[4], p[2], p[3]);
    print(message ?? { ok: true }, flags.json, () => 'replied');
    return 0;
  }
  if (cmd === 'changes' && p[1] === 'list') {
    const changes = await client.listChanges(p[2]);
    print(changes, flags.json, (cs) => cs.map((c) => `${c.kind} ${c.path}@${c.position} ${JSON.stringify(c.text.slice(0, 60))}`).join('\n') || 'no tracked changes');
    return 0;
  }
  if (cmd === 'edit') {
    const [, project, file] = p;
    if (!project || !file) throw new Error('usage: edit <project> <file> --old TEXT --new TEXT');
    let edits;
    if (flags.stdin) edits = JSON.parse(readFileSync(0, 'utf-8')).edits;
    else if (flags.old !== undefined && flags.new !== undefined) edits = [{ old: flags.old, new: flags.new }];
    else throw new Error('give --old and --new, or --stdin');
    const result = await client.editDocument(project, file, edits, { tracked: !flags.direct, dryRun: !!flags['dry-run'] });
    print(result, flags.json, (r) => r.applied ? `${r.tracked ? 'tracked' : 'direct'} edit applied to ${r.path}` : `dry run: ${r.ops.length} operation(s) for ${r.path}`);
    return 0;
  }
  if (cmd === 'pdf') {
    if (!p[1]) throw new Error('usage: pdf <project> [-o FILE]');
    const { pdf } = await client.renderPdf(p[1], { draft: !!flags.draft });
    const out = flags.o || 'output.pdf';
    writeFileSync(out, pdf);
    console.log(flags.json ? JSON.stringify({ file: out, bytes: pdf.length }) : `saved ${out} (${pdf.length} bytes)`);
    return 0;
  }
  if (cmd === 'create') {
    if (!p[1] || !p[2]) throw new Error('usage: create <project> <path> < content');
    const result = await client.createFile(p[1], p[2], readFileSync(0, 'utf-8'), { dryRun: !!flags['dry-run'] });
    print(result, flags.json, (r) => r.created ? `created ${r.path}${r.folders_created.length ? ` (new folders: ${r.folders_created.join(', ')})` : ''}` : `dry run: would create ${r.path}`);
    return 0;
  }
  if (cmd === 'check') {
    const comments = await client.listComments(p[1], { status: 'all' });
    console.log(`ok: ${comments.length} comment thread(s) readable`);
    return 0;
  }
  console.error(USAGE);
  return 2;
}

main(process.argv.slice(2)).then((code) => process.exit(code), (e) => { console.error(`error: ${e.message}`); process.exit(1); });
