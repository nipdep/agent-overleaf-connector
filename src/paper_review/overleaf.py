"""Native Overleaf review comments, through the community CLI ``olcli`` (MIT).

Select text in Overleaf, add a comment in its Review panel, and the agent sees the selected range
and your message; its reply appears in the same thread and the thread is resolved once the change
is accepted.

Overleaf has no public API for comments and they are not in git, so this uses ``olcli``, which talks
to the web editor's own API with your browser session cookie. This tool never sees the cookie:
credentials stay with ``olcli`` (``olcli auth --cookie ...`` or the ``OVERLEAF_SESSION`` variable).
Unofficial, so it can break when Overleaf changes; every failure here is a warning, never fatal.

Agent messages posted to a thread are prefixed ``[agent] `` (they appear under your account), which
is how they are told apart from yours and never re-imported as new feedback.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field

from . import anchor as anchor_mod
from .build import load_text
from .config import Config
from .gitutil import git, rev_parse
from .store import Store

AGENT_PREFIX = "[agent] "
INSTALL_HINT = ("install olcli (npm install -g @aloth/olcli), then run: olcli auth --cookie "
                "\"<your overleaf_session2 cookie>\"  (or set OVERLEAF_SESSION)")


class OverleafError(RuntimeError):
    pass


def enabled(cfg: Config) -> bool:
    return bool(cfg.overleaf_project)


def _base(cfg: Config) -> list[str]:
    return shlex.split(cfg.olcli)


def _run(cfg: Config, args: list[str], timeout: int = 240) -> str:
    cmd = _base(cfg) + args
    if not cmd or not shutil.which(cmd[0]):
        raise OverleafError(f"olcli not found: {INSTALL_HINT}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise OverleafError(f"olcli timed out after {timeout}s ({' '.join(args[:2])})") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise OverleafError(f"olcli {' '.join(args[:2])} failed: {detail[-1] if detail else 'no output'}"
                            " (an expired session cookie is the usual cause: olcli auth --cookie ...)")
    return proc.stdout


# ------------------------------------------------------------------------------ parsing
def _author(message: dict) -> str:
    user = message.get("user") or {}
    if isinstance(user, dict):
        name = user.get("email") or user.get("name") or " ".join(
            x for x in (user.get("first_name"), user.get("last_name")) if x)
        if name:
            return str(name)
    return str(message.get("user_id") or "unknown")


def parse_threads(raw: str) -> list[dict]:
    """Normalise ``olcli comments list --json`` output (a bare array, or ``{comments, changes}``)."""
    start = min((i for i in (raw.find("["), raw.find("{")) if i >= 0), default=-1)
    if start < 0:
        raise OverleafError("olcli printed no JSON")
    data = json.loads(raw[start:])
    items = data.get("comments", []) if isinstance(data, dict) else data
    out = []
    for c in items:
        tid = c.get("threadId") or c.get("thread_id") or c.get("id")
        if not tid:
            continue
        messages = []
        for m in c.get("messages") or []:
            text = m.get("content") if m.get("content") is not None else (m.get("text") or m.get("body") or "")
            messages.append({"id": str(m.get("id") or m.get("_id") or ""), "text": str(text),
                             "author": _author(m), "at": m.get("timestamp") or m.get("created_at")})
        out.append({
            "thread_id": str(tid),
            "doc_id": c.get("docId") or c.get("doc_id"),
            "path": str(c.get("path") or c.get("file") or "").lstrip("/").removeprefix("./"),
            "line": c.get("line"),
            "quote": c.get("selectedText") or c.get("selected_text") or c.get("quote") or "",
            "resolved": bool(c.get("resolved")),
            "messages": messages,
        })
    return out


def list_threads(cfg: Config, status: str = "all") -> list[dict]:
    args = ["comments", "list", cfg.overleaf_project, "--status", status, "--json"]
    raw = _run(cfg, args)
    try:
        return parse_threads(raw)
    except (json.JSONDecodeError, OverleafError):
        # some olcli versions only emit JSON together with --changes
        return parse_threads(_run(cfg, args + ["--changes"]))


def reply(cfg: Config, thread_id: str, text: str) -> None:
    _run(cfg, ["comments", "reply", thread_id, text, cfg.overleaf_project, "--json"])


def resolve(cfg: Config, thread_id: str) -> None:
    _run(cfg, ["comments", "resolve", thread_id, cfg.overleaf_project, "--json"])


# ------------------------------------------------------------------------------ import
@dataclass
class OverleafSync:
    created: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)
    resolved_in_overleaf: list[str] = field(default_factory=list)
    reopened_in_overleaf: list[str] = field(default_factory=list)
    deleted_in_overleaf: list[str] = field(default_factory=list)
    changed: bool = False


def _locate(cfg: Config, rel: str, quote: str, line: int | None) -> tuple[int | None, float]:
    """Line of ``quote`` in the working tree and how sure we are."""
    f = cfg.root / rel
    if not rel or not f.is_file():
        return line, 0.0
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    first = (quote.strip().splitlines() or [""])[0].strip()
    if line and 1 <= line <= len(lines) and first and first in lines[line - 1]:
        return line, 1.0
    if first:
        for i, l in enumerate(lines, start=1):
            if first in l:
                return i, 0.9
    return line, 0.4 if line else 0.0


def _build_anchor(cfg: Config, t: dict, pages: list[dict]) -> dict:
    line, conf = _locate(cfg, t["path"], t["quote"], t["line"])
    plain = anchor_mod.latex_to_plain(t["quote"])
    page = anchor_mod.find_page(plain, pages) if pages and plain else None
    return {"build_commit": rev_parse(cfg.root, "HEAD"), "page": page[0] if page else None,
            "quote": t["quote"], "source": {"file": t["path"], "line": line, "confidence": conf}}


def _entry(m: dict, kind: str = "follow-up") -> dict:
    return {"type": kind, "author": f"human:{m['author']}", "at": m["at"] or "", "body": m["text"]}


def import_comments(cfg: Config) -> OverleafSync:
    """Mirror Overleaf's comment threads into ``review/comments/``."""
    result = OverleafSync()
    store = Store(cfg)
    pages = load_text(cfg)
    threads = list_threads(cfg, "all")
    present: set[str] = set()

    for t in threads:
        ext = f"overleaf:{t['thread_id']}"
        present.add(ext)
        human = [m for m in t["messages"] if not m["text"].startswith(AGENT_PREFIX)]
        if not human:
            continue
        existing = store.by_external(ext)
        if existing is None:
            if t["resolved"]:
                continue  # never import threads that were already closed
            first = human[0]
            c = store.new(
                body=first["text"], author=f"human:{first['author']}", kind="comment",
                anchor=_build_anchor(cfg, t, pages),
                origin={"type": "overleaf", "external_id": ext, "thread_id": t["thread_id"],
                        "doc_id": t["doc_id"], "messages_seen": [m["id"] for m in human]},
            )
            for m in human[1:]:
                c["thread"].append(_entry(m))
            store.save(c)
            result.created.append(c["id"])
            continue

        origin = existing.setdefault("origin", {})
        seen = set(origin.get("messages_seen", []))
        fresh = [m for m in human if m["id"] not in seen]
        dirty = False
        if fresh:
            existing["thread"].extend(_entry(m) for m in fresh)
            origin["messages_seen"] = sorted(seen | {m["id"] for m in fresh})
            if existing["status"] != "open":
                existing["status"], existing["resolution"] = "open", None
                result.reopened_in_overleaf.append(existing["id"])
            result.followups.append(existing["id"])
            dirty = True
        if t["resolved"] and existing["status"] in {"open", "addressed"}:
            existing["status"] = "resolved"
            existing["resolution"] = {"by": "human", "note": "Resolved in Overleaf.", "at": ""}
            origin["resolve_pushed"] = True
            result.resolved_in_overleaf.append(existing["id"])
            dirty = True
        elif not t["resolved"] and existing["status"] == "resolved" and origin.get("resolve_pushed"):
            existing["status"], existing["resolution"] = "open", None  # reopened in Overleaf
            origin["resolve_pushed"] = False
            result.reopened_in_overleaf.append(existing["id"])
            dirty = True
        if dirty:
            store.save(existing)

    for c in store.all():
        origin = c.get("origin", {})
        if origin.get("type") == "overleaf" and origin["external_id"] not in present \
                and c["status"] in {"open", "addressed"}:
            c["status"] = "wontfix"
            c["resolution"] = {"by": "paper-review", "note": "Thread deleted in Overleaf.", "at": ""}
            store.save(c)
            result.deleted_in_overleaf.append(c["id"])
    result.changed = bool(result.created or result.followups or result.resolved_in_overleaf
                          or result.reopened_in_overleaf or result.deleted_in_overleaf)
    return result


# ------------------------------------------------------------------------------ write back
def _agent_replies(c: dict) -> list[str]:
    return [t["body"].strip() for t in c.get("thread", [])
            if str(t.get("author", "")).startswith("agent") and t.get("body", "").strip()]


def _effective(cfg: Config, store: Store, agent_branch: str | None) -> list[dict]:
    """Local comments, using the agent branch's copy when it has more of the conversation."""
    out = []
    for c in store.all():
        if (c.get("origin") or {}).get("type") != "overleaf":
            continue
        if agent_branch:
            raw = git(cfg.root, "show", f"{agent_branch}:{cfg.review_dir}/comments/{c['id']}.json", check=False)
            if raw.strip():
                try:
                    on_branch = json.loads(raw)
                    if len(on_branch.get("thread", [])) > len(c.get("thread", [])):
                        c = {**c, "thread": on_branch["thread"]}
                except json.JSONDecodeError:
                    pass
        out.append(c)
    return out


def reconcile(cfg: Config, agent_branch: str | None = None) -> dict:
    """Post the agent's replies into their Overleaf threads and resolve accepted ones.

    Idempotent without local state: a reply is posted only if no message with exactly that text is
    in the thread yet; a thread is resolved only if it is still open there.
    """
    store = Store(cfg)
    threads = {t["thread_id"]: t for t in list_threads(cfg, "all")}
    posted: list[str] = []
    resolved: list[str] = []
    for c in _effective(cfg, store, agent_branch):
        origin = c["origin"]
        t = threads.get(origin.get("thread_id", ""))
        if t is None:
            continue
        have = {m["text"].strip() for m in t["messages"]}
        for text in _agent_replies(c):
            msg = AGENT_PREFIX + text
            if msg.strip() not in have:
                reply(cfg, t["thread_id"], msg)
                have.add(msg.strip())
                posted.append(c["id"])
        stored = store.get(c["id"])
        if stored["status"] == "resolved" and not t["resolved"] and not stored["origin"].get("resolve_pushed"):
            resolve(cfg, t["thread_id"])
            stored["origin"]["resolve_pushed"] = True
            store.save(stored)
            resolved.append(c["id"])
    return {"replies_posted": posted, "threads_resolved": resolved}


def check(cfg: Config) -> dict:
    """Used by ``overleaf-check``: can we reach the project's threads?"""
    threads = list_threads(cfg, "all")
    return {"project": cfg.overleaf_project, "threads": len(threads),
            "open": sum(1 for t in threads if not t["resolved"]),
            "with_selected_text": sum(1 for t in threads if t["quote"])}
