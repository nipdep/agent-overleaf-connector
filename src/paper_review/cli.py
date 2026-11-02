"""paper-review command line. Every listing command supports ``--json``."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import __version__
from .apply import ApplyError, apply
from .build import BuildError, build
from .changelog import write_changelog
from .config import CONFIG_NAME, Config, detect_engine, detect_main, find_root, load_config
from .gitutil import GitError, default_branch, git, rev_parse
from .init import DEFAULT_USES, init
from .local import LocalError, pull, push
from .redline import RedlineError, generate
from .store import Store
from .sync import sync


def _emit(args, data, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if getattr(args, "json", False) else text)


def _cfg(args) -> Config:
    return load_config(Path(args.root).resolve() if args.root else find_root())


def cmd_init(args, cfg):
    for line in init(cfg, mode=args.mode, uses=args.uses, workflow=not (args.no_workflow or args.local), force=args.force, local=args.local):
        print(line)
    print("Next: review the new files, commit and push them.")


def cmd_build(args, cfg):
    info = build(cfg)
    _emit(args, info, f"built {info['pages']} page(s) with {info['engine']} -> {cfg.build_dir}/paper.pdf "
                      f"({info['latex_warnings']} warnings, {info['overfull_boxes']} overfull boxes)")


def cmd_sync(args, cfg):
    r = sync(cfg)
    _emit(args, r.__dict__, f"created {r.created}, reopened {r.reopened}, addressed {r.addressed}, updated {r.updated}")


def _row(c: dict) -> str:
    src = c["anchor"].get("source") or {}
    where = f"{src.get('file', '-')}:{src.get('line', '-')}"
    page = c["anchor"].get("page")
    body = c["body"].replace("\n", " ")
    return f"{c['id']}  {c['status']:<9} p{page if page else '-':<3} {where:<28} {body[:70]}"


def cmd_list(args, cfg):
    items = Store(cfg).all()
    if args.status:
        items = [c for c in items if c["status"] in args.status]
    _emit(args, items, "\n".join(_row(c) for c in items) or "no comments")


def cmd_show(args, cfg):
    c = Store(cfg).get(args.id)
    src = c["anchor"].get("source") or {}
    context = ""
    f = cfg.root / src.get("file", "")
    if src.get("file") and f.is_file():
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        n = src.get("line", 1)
        lo, hi = max(0, n - 1 - args.context), min(len(lines), n + args.context + 8)
        context = "\n".join(f"{i + 1:>5}  {lines[i]}" for i in range(lo, hi))
    page = c["anchor"].get("page")
    img = cfg.build_path / "pages" / f"p-{page:03d}.png" if page else None
    data = {**c, "context": context, "page_image": str(img) if img and img.exists() else None}
    text = [f"{c['id']}  [{c['status']}]  {c['kind']}  by {c['author']}", "", c["body"], ""]
    text.append(f"source: {src.get('file')}:{src.get('line')}   page: {page}")
    if data["page_image"]:
        text.append(f"page image: {img}")
    if c["anchor"].get("quote"):
        text.append(f"text: {c['anchor']['quote'][:300]}")
    if context:
        text += ["", context]
    for t in c["thread"]:
        text.append(f"\n[{t['author']} {t['at']}] {t['body']}")
    _emit(args, data, "\n".join(text))


def cmd_reply(args, cfg):
    Store(cfg).reply(args.id, args.author, args.text)
    print(f"replied to {args.id}")


def cmd_resolve(args, cfg):
    status = "resolved" if cfg.mode == "direct" else "addressed"
    extra = {"by": args.author, "note": args.note or ""}
    if args.commit:
        extra["commit"] = rev_parse(cfg.root, args.commit) or args.commit
    Store(cfg).set_status(args.id, status, **extra)
    print(f"{args.id} -> {status}")


def cmd_round(args, cfg):
    out = git(cfg.root, "branch", "-a", "--format=%(refname:short)", check=False)
    nums = [int(m.group(1)) for l in out.split() if (m := re.search(r"agent/round-(\d+)$", l))]
    print(f"agent/round-{max(nums) + 1 if nums else 1}")


def cmd_redline(args, cfg):
    base = args.base or default_branch(cfg.root, cfg.default_branch)
    meta = generate(cfg, base, args.head, branch=args.head)
    _emit(args, meta, f"{len(meta['entries'])} change(s) -> {cfg.review_dir}/redline.tex"
                      + "".join(f"\n  warning: {w}" for w in meta.get("warnings", [])))


def cmd_apply(args, cfg):
    r = apply(cfg)
    _emit(args, r, str(r))


def cmd_changelog(args, cfg):
    changed = write_changelog(cfg)
    print(f"{cfg.review_dir}/CHANGELOG.md {'updated' if changed else 'unchanged'}")


def cmd_ci(args, cfg):
    from .ci import run

    r = run(cfg, branch=args.branch, push=args.push)
    print("\n".join(r["log"]) or "ok")
    return 0 if r["ok"] else 1


def cmd_pull(args, cfg):
    r = pull(cfg)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    lines = [f"pulled {r['fetched_commits']} commit(s) from {r['remote']}"
             + (f" (changed: {', '.join(r['files'][:8])}{' ...' if len(r['files']) > 8 else ''})" if r["files"] else "")]
    c = r["comments"]
    lines.append("comments: " + ", ".join(f"{len(v)} {k.replace('_', ' ')} ({', '.join(v)})" for k, v in c.items() if v)
                 if any(c.values()) else "comments: no changes from the researcher")
    d = r["decisions"]
    if d and d.get("status") == "applied":
        lines.append(f"decisions applied: accepted {d['accepted'] or 'none'}, rejected {d['rejected'] or 'none'}, "
                     f"still pending {d['pending'] or 'none'}")
    lines.append(f"redline: {r['redline']}")
    for w in r["warnings"]:
        lines.append(f"WARNING: {w}")
    lines.append(f"open comments ({len(r['open'])}):")
    for o in r["open"]:
        where = f"{o['file']}:{o['line']}" if o["file"] else "-"
        lines.append(f"  {o['id']}  {where:<30} {o['body'][:80]}")
        for t in o["thread"]:
            lines.append(f"      reply: {t[:100]}")
    print("\n".join(lines))


def cmd_push(args, cfg):
    r = push(cfg)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    print(f"pushed to {r['remote']} (redline: {r['redline']})")
    for w in r["warnings"]:
        print(f"WARNING: {w}")


def cmd_doctor(args, cfg):
    ok = True

    def check(label: str, good: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"[{'ok' if good else 'FAIL'}] {label} {detail}".rstrip())

    check("git", bool(shutil.which("git")))
    check("latexmk", bool(shutil.which("latexmk")), "" if shutil.which("latexmk") else "(install TeX Live or use docker/Dockerfile)")
    check("latexdiff", bool(shutil.which("latexdiff")), "" if shutil.which("latexdiff") else "(needed for redlines)")
    try:
        main = detect_main(cfg)
        engine, how = detect_engine(cfg)
        check("main file", True, main)
        print(f"[info] engine {engine} (from {how})")
        if how.startswith("default"):
            print("[warn] Overleaf's compiler/TeX Live version are project settings, not in git. "
                  f"Set 'engine' in {CONFIG_NAME} if your project does not use pdflatex.")
    except FileNotFoundError as exc:
        check("main file", False, str(exc))
    check("config", (cfg.root / CONFIG_NAME).exists(), "" if (cfg.root / CONFIG_NAME).exists() else "(run: paper-review init)")
    print(f"[info] mode {cfg.mode}, default branch {default_branch(cfg.root, cfg.default_branch)}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="paper-review", description=__doc__)
    p.add_argument("--root", help="repository root (default: auto-detect)")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, json_=False):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if json_:
            sp.add_argument("--json", action="store_true", help="machine-readable output")
        return sp

    sp = add("init", cmd_init, "add config, workflow and agent instructions to a repo")
    sp.add_argument("--mode", choices=["direct", "suggest"], default="direct")
    sp.add_argument("--uses", default=DEFAULT_USES, help="reusable workflow reference")
    sp.add_argument("--no-workflow", action="store_true", help="skip the GitHub workflow file")
    sp.add_argument("--local", action="store_true", help="local-first mode (pull/push, no CI): implies --no-workflow")
    sp.add_argument("--force", action="store_true", help="overwrite existing files")
    add("build", cmd_build, "build PDF, page images and text.json", True)
    add("sync", cmd_sync, "turn %% @agent markers into comments", True)
    sp = add("list", cmd_list, "list comments", True)
    sp.add_argument("--status", nargs="+", choices=["open", "addressed", "resolved", "wontfix", "stale"])
    sp = add("show", cmd_show, "show one comment with source context", True)
    sp.add_argument("id")
    sp.add_argument("--context", type=int, default=4, help="source lines of context")
    sp = add("reply", cmd_reply, "reply on a comment")
    sp.add_argument("id")
    sp.add_argument("text")
    sp.add_argument("--author", default="agent")
    sp = add("resolve", cmd_resolve, "mark a comment addressed (suggest mode) or resolved (direct mode)")
    sp.add_argument("id")
    sp.add_argument("--note")
    sp.add_argument("--commit")
    sp.add_argument("--author", default="agent")
    add("round", cmd_round, "print the next agent branch name, e.g. agent/round-3").set_defaults(fn=cmd_round)
    sp = add("redline", cmd_redline, "generate review/redline.tex for an agent branch", True)
    sp.add_argument("head", help="agent branch or commit")
    sp.add_argument("--base", help="base ref (default: the default branch)")
    add("apply", cmd_apply, "apply accept/reject decisions from review/redline.tex", True)
    add("pull", cmd_pull, "before an agent task: fetch the researcher's edits and report what happened to the comments", True)
    add("push", cmd_push, "after an agent task: refresh the redline and publish the default branch", True)
    add("changelog", cmd_changelog, "regenerate review/CHANGELOG.md")
    sp = add("ci", cmd_ci, "run the CI steps for the current branch")
    sp.add_argument("--branch")
    sp.add_argument("--push", action="store_true")
    add("doctor", cmd_doctor, "check the environment and configuration")

    args = p.parse_args(argv)
    try:
        return args.fn(args, _cfg(args)) or 0
    except (BuildError, RedlineError, ApplyError, LocalError, GitError, KeyError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
