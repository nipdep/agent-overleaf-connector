"""What the GitHub workflow runs after the paper is built (``paper-review ci``).

* push to the default branch: bootstrap files on first run, sync markers into
  comments, apply accept/reject decisions if the researcher made any, refresh the
  change log;
* push to ``agent/*``: regenerate ``review/redline.tex`` on the default branch.

Bot commits carry ``[skip ci]``. With ``push=True`` the results are pushed.
"""

from __future__ import annotations

from pathlib import Path

from .apply import ApplyError, apply, ensure_identity, pending_decisions
from .changelog import write_changelog
from .config import CONFIG_NAME, Config
from .gitutil import commit_paths, current_branch, default_branch, git, rev_parse
from .init import init
from .redline import generate
from .sync import sync

SUFFIX = " [skip ci]"


def _push(root: Path, ref: str, remote: str = "origin") -> None:
    try:
        git(root, "push", remote, ref)
    except Exception:
        # Overleaf may have pushed meanwhile: rebase our bot commits and retry once.
        git(root, "pull", "--rebase", remote, ref)
        git(root, "push", remote, ref)


def run(cfg: Config, branch: str | None = None, push: bool = False) -> dict:
    root = cfg.root
    ensure_identity(root)
    default = default_branch(root, cfg.default_branch)
    branch = branch or current_branch(root) or default
    remote = "origin" if git(root, "remote", check=False).strip() else None
    log: list[str] = []

    if branch == default:
        if not (root / CONFIG_NAME).exists():
            log += init(cfg, workflow=False)
            commit_paths(root, [CONFIG_NAME, "AGENTS.md", "CLAUDE.md", ".gitignore", cfg.review_dir],
                         f"paper-review: add configuration and agent instructions{SUFFIX}")
        res = sync(cfg)
        if res.changed:
            commit_paths(root, [f"{cfg.review_dir}/comments"],
                         f"paper-review: sync comments (+{len(res.created)} new, {len(res.addressed)} addressed){SUFFIX}")
            log.append(f"sync: {len(res.created)} created, {len(res.reopened)} reopened, {len(res.addressed)} addressed")
        if pending_decisions(cfg):
            try:
                result = apply(cfg, message_suffix=SUFFIX)
                log.append(f"apply: {result}")
                if push and remote:
                    _push(root, default, remote)
                    if result.get("tag"):  # keep the rollback point beyond this runner
                        git(root, "push", remote, f"refs/tags/{result['tag']}")
                    b = result.get("branch")
                    if b and result.get("branch_action") == "recreated":
                        git(root, "push", "--force", remote, f"{b}:refs/heads/{b}")
                    elif b and result.get("branch_action") == "deleted":
                        git(root, "push", remote, "--delete", b, check=False)
            except ApplyError as exc:
                log.append(f"apply FAILED: {exc}")
                return {"ok": False, "log": log}
        if write_changelog(cfg):
            commit_paths(root, [f"{cfg.review_dir}/CHANGELOG.md"], f"paper-review: update change log{SUFFIX}")
        if push and remote:
            _push(root, default, remote)
        return {"ok": True, "log": log}

    if branch.startswith("agent/"):
        head_sha = rev_parse(root, "HEAD")
        if remote:
            git(root, "fetch", remote, default, check=False)
        target = f"origin/{default}" if remote and rev_parse(root, f"origin/{default}") else default
        git(root, "checkout", "-q", "-B", default, target)
        meta = generate(cfg, default, head_sha, branch=branch)
        commit_paths(root, [f"{cfg.review_dir}/redline.tex", f"{cfg.review_dir}/redline.json", f"{cfg.review_dir}/assets"],
                     f"paper-review: redline for {branch} ({len(meta['entries'])} change(s)){SUFFIX}")
        log.append(f"redline: {len(meta['entries'])} change(s) from {branch}")
        if push and remote:
            _push(root, default, remote)
        return {"ok": True, "log": log}

    return {"ok": True, "log": [f"nothing to do on branch {branch!r}"]}
