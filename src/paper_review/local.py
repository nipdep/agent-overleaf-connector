"""Local-first workflow: no CI, no polling, no manual push/pull buttons.

The clone of the Overleaf Git remote (or any git remote) lives on the machine
where the agent runs. Two explicit steps wrap an agent task:

``pull``  before the task: fetch what the researcher did in Overleaf, turn their
          ``%% @agent:`` markers into comments, apply their accept/reject lines,
          and report what happened to the comments.
``push``  after the task: refresh ``review/redline.tex`` from the agent branch,
          update the change log, and publish the default branch to the remote.

The agent branch (``agent/round-N``) stays local; only the default branch is
pushed, which also suits Overleaf's single-branch (``master``) Git server.
History on the default branch is kept linear (fast-forward or rebase, never a
merge commit).
"""

from __future__ import annotations

import json
import re

from .apply import ApplyError, apply, ensure_identity, pending_decisions
from .changelog import write_changelog
from .config import Config
from .gitutil import (GitError, commit_paths, commits_between, current_branch, default_branch, git,
                      has_changes_outside, is_clean, rev_parse)
from .redline import RedlineError, generate
from .store import Store
from .sync import sync


class LocalError(RuntimeError):
    pass


def _setup(cfg: Config) -> tuple[str, str, str]:
    """Validate the repo state; return ``(default_branch, remote, remote_branch)``."""
    root = cfg.root
    ensure_identity(root)
    remote = cfg.remote
    if remote not in git(root, "remote").split():
        raise LocalError(f"git remote {remote!r} not found; clone your Overleaf project "
                         f"or set 'remote' in .paper-review.yml")
    default = default_branch(root, cfg.default_branch)
    if not is_clean(root):
        raise LocalError("working tree has uncommitted changes; commit or stash them first")
    if current_branch(root) != default:
        git(root, "switch", "-q", default)
    return default, remote, cfg.remote_branch or default


def agent_branch(cfg: Config) -> str | None:
    """Highest-numbered local ``agent/round-N`` branch, if any."""
    names = git(cfg.root, "branch", "--format=%(refname:short)", "--list", "agent/round-*").split()
    nums = [(int(m.group(1)), n) for n in names if (m := re.search(r"round-(\d+)$", n))]
    return max(nums)[1] if nums else None


def _integrate(cfg: Config, remote: str, rbranch: str) -> dict:
    """Fetch and bring the default branch up to date, keeping history linear."""
    root = cfg.root
    git(root, "fetch", "-q", remote)
    ref = f"{remote}/{rbranch}"
    if not rev_parse(root, ref):
        raise LocalError(f"remote branch {ref} not found")
    before = rev_parse(root, "HEAD")
    behind = int(git(root, "rev-list", "--count", f"HEAD..{ref}").strip())
    if behind == 0:
        return {"fetched_commits": 0, "files": []}
    git(root, "merge", "--ff-only", "-q", ref, check=False)
    if rev_parse(root, "HEAD") == before:  # diverged: local commits not on the remote yet
        try:
            git(root, "rebase", "-q", ref)
        except GitError as exc:
            git(root, "rebase", "--abort", check=False)
            raise LocalError(
                f"your Overleaf edits conflict with local commits that are not pushed yet; "
                f"nothing was changed. Resolve manually (git rebase {ref}). Details: {exc}") from exc
    files = git(root, "diff", "--name-only", before, "HEAD", check=False).split()
    return {"fetched_commits": behind, "files": files}


def _refresh_agent(cfg: Config, default: str) -> dict:
    """Keep the agent branch based on the default branch and the redline current."""
    root = cfg.root
    out: dict = {"redline": "unchanged", "warnings": []}
    branch = agent_branch(cfg)
    meta_path = cfg.review_path / "redline.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    paths = [f"{cfg.review_dir}/redline.tex", f"{cfg.review_dir}/redline.json", f"{cfg.review_dir}/assets"]

    if branch and commits_between(root, default, branch):
        # Rebase only if the default branch moved in the paper itself (the redline files
        # we commit to it do not count, or every pull would rebase again).
        fork = git(root, "merge-base", default, branch).strip()
        if has_changes_outside(root, fork, default, cfg.review_dir):
            try:
                git(root, "rebase", "-q", default, branch)
            except GitError as exc:
                git(root, "rebase", "--abort", check=False)
                git(root, "switch", "-q", default, check=False)
                out["warnings"].append(
                    f"{branch} conflicts with the researcher's Overleaf edits and was left as it was; "
                    f"the agent must rebase it onto {default} and resolve the conflict ({exc})")
            else:
                git(root, "switch", "-q", default)
        head = rev_parse(root, branch)
        if meta and meta.get("head") == head and meta.get("base") \
                and not has_changes_outside(root, meta["base"], default, cfg.review_dir):
            return out  # redline already current
        try:
            m = generate(cfg, default, branch, branch=branch)
        except RedlineError as exc:
            out["warnings"].append(f"redline not updated: {exc}")
            return out
        out["redline"] = f"{len(m['entries'])} change(s) from {branch}"
    elif meta and meta.get("entries"):
        generate(cfg, default, None)
        out["redline"] = "reset (no pending agent changes)"
    else:
        return out
    commit_paths(root, paths, "paper-review: update redline")
    return out


def pull(cfg: Config) -> dict:
    """Fetch from the remote and report what the researcher did."""
    default, remote, rbranch = _setup(cfg)
    root = cfg.root
    summary: dict = {"remote": f"{remote}/{rbranch}", "warnings": []}
    summary.update(_integrate(cfg, remote, rbranch))

    res = sync(cfg)
    if res.changed:
        commit_paths(root, [f"{cfg.review_dir}/comments"],
                     f"paper-review: sync comments (+{len(res.created)} new, {len(res.addressed)} addressed)")
    summary["comments"] = {"new": res.created, "reopened": res.reopened,
                           "removed_by_researcher": res.addressed, "updated": res.updated}

    summary["decisions"] = None
    if pending_decisions(cfg):
        try:
            summary["decisions"] = apply(cfg)
        except ApplyError as exc:
            summary["warnings"].append(f"decisions in redline.tex were not applied: {exc}")

    agent = _refresh_agent(cfg, default)
    summary["redline"] = agent["redline"]
    summary["warnings"] += agent["warnings"]
    summary["agent_branch"] = agent_branch(cfg)
    summary["open"] = [
        {"id": c["id"], "body": c["body"], "file": (c["anchor"].get("source") or {}).get("file"),
         "line": (c["anchor"].get("source") or {}).get("line"),
         "thread": [t["body"] for t in c["thread"]]}
        for c in Store(cfg).all() if c["status"] == "open"
    ]
    return summary


def push(cfg: Config) -> dict:
    """Refresh the redline and change log, then publish the default branch."""
    default, remote, rbranch = _setup(cfg)
    root = cfg.root
    out: dict = {"remote": f"{remote}/{rbranch}", "warnings": []}
    for attempt in (1, 2):
        agent = _refresh_agent(cfg, default)
        out["redline"] = agent["redline"]
        out["warnings"] += agent["warnings"]
        if write_changelog(cfg):
            commit_paths(root, [f"{cfg.review_dir}/CHANGELOG.md"], "paper-review: update change log")
        git(root, "fetch", "-q", remote, check=False)
        known = rev_parse(root, f"{remote}/{rbranch}")
        out["pushed_commits"] = int(git(root, "rev-list", "--count", f"{known}..HEAD").strip()) if known else None
        try:
            git(root, "push", "-q", remote, f"{default}:{rbranch}")
            return out
        except GitError as exc:
            if attempt == 2:
                raise LocalError(f"push rejected twice: {exc}") from exc
            _integrate(cfg, remote, rbranch)  # the researcher pushed meanwhile: take it, retry once
    return out
