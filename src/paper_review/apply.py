"""Apply the human's accept/reject decisions from ``redline.tex``.

* accepted commits are cherry-picked onto the default branch (in order);
* rejected commits are dropped and their comments reopened with the reason;
* pending commits stay on a re-created agent branch for the next review.

Everything happens after tagging the starting point, and a conflict rolls the
whole operation back (nothing is half-applied).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import Config
from .gitutil import GitError, auto_resolve_comment_conflicts, commit_paths, current_branch, default_branch, git, is_clean, resolve_ref, rev_parse
from .redline import RedlineError, generate, parse_decisions
from .store import Store


class ApplyError(RuntimeError):
    pass


def ensure_identity(root) -> None:
    if not git(root, "config", "user.email", check=False).strip():
        git(root, "config", "user.email", "paper-review[bot]@users.noreply.github.com")
    if not git(root, "config", "user.name", check=False).strip():
        git(root, "config", "user.name", "paper-review[bot]")


def pending_decisions(cfg: Config) -> bool:
    """True if redline.tex holds at least one accept/reject decision."""
    tex = cfg.redline_path
    if not tex.exists() or not (cfg.review_path / "redline.json").exists():
        return False
    return any(d["decision"] != "pending" for d in parse_decisions(tex.read_text(encoding="utf-8")).values())


def _cherry_pick(root, shas: list[str], undo_to: str, review_dir: str = "review") -> None:
    for sha in shas:
        try:
            git(root, "cherry-pick", "--allow-empty", "--keep-redundant-commits", sha)
        except GitError as exc:
            # a follow-up from the researcher and the agent's reply can both have edited one comment
            # file; merge those. A conflict in the paper itself still stops everything.
            if auto_resolve_comment_conflicts(root, review_dir):
                try:
                    git(root, "-c", "core.editor=true", "cherry-pick", "--continue")
                    continue
                except GitError as exc2:
                    exc = exc2
            git(root, "cherry-pick", "--abort", check=False)
            git(root, "reset", "--hard", undo_to)
            raise ApplyError(f"conflict applying {sha[:7]}: {exc}") from exc


def apply(cfg: Config, message_suffix: str = "", extra_decisions: dict | None = None) -> dict:
    """``extra_decisions`` (e.g. from Overleaf threads) fill in entries still ``pending`` in redline.tex;
    a decision typed in redline.tex wins."""
    root = cfg.root
    ensure_identity(root)
    meta_path = cfg.review_path / "redline.json"
    if not meta_path.exists():
        raise ApplyError("no review/redline.json; nothing to apply")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    entries = meta.get("entries", [])
    default = default_branch(root, cfg.default_branch)
    if current_branch(root) != default:
        raise ApplyError(f"apply must run on the default branch {default!r}, not {current_branch(root)!r}")
    if not is_clean(root):
        raise ApplyError("working tree is not clean; commit or stash first")
    branch = meta.get("branch")
    tip = resolve_ref(root, branch) if branch else None
    if not tip:
        raise ApplyError(f"agent branch {branch!r} not found")
    if tip != meta.get("head"):
        raise ApplyError("the agent branch moved since this redline was generated; regenerate it first")

    decisions = parse_decisions(cfg.redline_path.read_text(encoding="utf-8"))
    for key, d in (extra_decisions or {}).items():
        if decisions.get(key, {}).get("decision", "pending") == "pending":
            decisions[key] = d
    star = decisions.get("*", {}).get("decision")
    accepted, rejected, pending = [], [], []
    for e in entries:
        d = decisions.get(e["key"], {"decision": "pending", "reason": ""})
        value = d["decision"]
        if value == "pending" and star in {"accept-all", "reject-all", "accept", "reject"}:
            value = star.split("-")[0]
        if value in {"accept", "accept-all"}:
            accepted.append(e)
        elif value in {"reject", "reject-all"}:
            rejected.append((e, d))
        else:
            pending.append(e)
    if not accepted and not rejected:
        return {"status": "nothing-to-do", "pending": [e["key"] for e in pending]}

    pre = rev_parse(root, "HEAD")
    tag = "paper-review/pre-apply-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    git(root, "tag", tag, pre)

    for e in accepted:
        _cherry_pick(root, e["shas"], pre, cfg.review_dir)

    store = Store(cfg)
    for e in accepted:
        for cid in e["comment_ids"]:
            try:
                store.set_status(cid, "resolved", by="human", decision="accept", commit=e["shas"][-1])
            except KeyError:
                pass
    for e, d in rejected:
        reason = d.get("reason", "")
        for cid in e["comment_ids"]:
            try:
                store.set_status(cid, "open")
                if d.get("source") != "overleaf":  # a reply typed in Overleaf is already in the thread
                    store.reply(cid, "human", "Rejected" + (f": {reason}" if reason else "."))
            except KeyError:
                pass
    names = lambda items: ", ".join(i["key"] if isinstance(i, dict) else i[0]["key"] for i in items) or "none"  # noqa: E731
    commit_paths(root, [f"{cfg.review_dir}/comments"],
                 f"paper-review: record decisions (accepted: {names(accepted)}; rejected: {names(rejected)}){message_suffix}")

    branch_action = "deleted"
    if pending:
        branch_action = _recreate_branch(root, default, branch, [s for e in pending for s in e["shas"]],
                                         cfg.review_dir)
    else:
        git(root, "branch", "-D", branch, check=False)

    new_head = branch if branch_action != "deleted" else None
    generate(cfg, default, new_head, branch=branch if new_head else None)
    commit_paths(root, cfg.redline_files,
                 f"paper-review: update redline{message_suffix}")
    return {
        "status": "applied",
        "tag": tag,
        "accepted": [e["key"] for e in accepted],
        "rejected": [e["key"] for e, _ in rejected],
        "pending": [e["key"] for e in pending],
        "branch": branch,
        "branch_action": branch_action,
    }


def _recreate_branch(root, default: str, branch: str, shas: list[str], review_dir: str = "review") -> str:
    base = rev_parse(root, "HEAD")
    tmp = "paper-review-tmp"
    git(root, "checkout", "-q", "-B", tmp, base)
    try:
        _cherry_pick(root, shas, base, review_dir)
    except ApplyError:
        git(root, "checkout", "-q", default)
        git(root, "branch", "-D", tmp, check=False)
        return "kept-old (pending commits conflict with accepted ones; resolve on the branch)"
    git(root, "branch", "-f", branch, tmp)
    git(root, "checkout", "-q", default)
    git(root, "branch", "-D", tmp)
    return "recreated"
