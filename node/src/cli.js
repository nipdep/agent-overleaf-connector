#!/usr/bin/env node
// olmcp-overleaf: the command line for the Overleaf client. Its comment commands accept the same arguments
// the Python tool passed to olcli, so `olcli: olmcp-overleaf` in .olmcp.yml is all it takes to switch.
import { readFileSync } from 'node:fs';
import { OverleafClient } from './client.js';
import { configPath, loadConfig, saveConfig } from './config.js';

const USAGE = `olmcp-overleaf <command>

  auth --cookie VALUE [--base-url URL] [--cookie-name NAME]   store the session cookie (mode 0600)
  comments list <project> [--status all|open|resolved] [--json]
  comments reply <thread> <text> <project> [--json]
  changes list <project> [--json]
  edit <project> <file> (--old TEXT --new TEXT | --stdin) [--direct] [--dry-run] [--json]
       --stdin reads {"edits":[{"old":"...","new":"..."}]}; edits are tracked changes unless --direct
  check <project>

There is no command to resolve, reopen or delete a comment thread.`;

function parse(argv) {
  const positional = []; const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      if (['json', 'stdin', 'direct', 'dry-run', 'changes'].includes(key)) flags[key] = true;
      else flags[key] = argv[++i];
    } else positional.push(a);
  }
  return { positional, flags };
}

const print = (data, json, text) => console.log(json ? JSON.stringify(data, null, 2) : text(data));

async function main(argv) {
  const { positional: p, flags } = parse(argv);
  const cmd = p[0];
  if (!cmd || cmd === 'help' || flags.help) { console.log(USAGE); return 0; }
  if (cmd === 'auth') {
    if (!flags.cookie) throw new Error('usage: olmcp-overleaf auth --cookie <value>');
    saveConfig({ sessionCookie: flags.cookie, ...(flags['base-url'] ? { baseUrl: flags['base-url'] } : {}),
      ...(flags['cookie-name'] ? { cookieName: flags['cookie-name'] } : {}) });
    console.log(`saved to ${configPath()}`);
    return 0;
  }
  if (cmd === 'comments' && ['resolve', 'reopen', 'delete'].includes(p[1])) {
    throw new Error(`"comments ${p[1]}" does not exist in olmcp-overleaf: resolving, reopening and deleting threads is left to the researcher in Overleaf`);
  }
  const client = await OverleafClient.connect(loadConfig());
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
  if (cmd === 'check') {
    const comments = await client.listComments(p[1], { status: 'all' });
    console.log(`ok: ${comments.length} comment thread(s) readable`);
    return 0;
  }
  console.error(USAGE);
  return 2;
}

main(process.argv.slice(2)).then((code) => process.exit(code), (e) => { console.error(`error: ${e.message}`); process.exit(1); });
