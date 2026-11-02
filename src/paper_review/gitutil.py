"""Small git helpers. All calls shell out to the ``git`` binary."""

from __future__ import annotations

import io
import re
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

CID_RE = re.compile(r"\bC-\d{4,}\b")
_RESOLVES = re.compile(r"^Resolves:\s*(.+)$", re.M | re.I)


class GitError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True, input: str | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, input=input
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def rev_parse(root: Path, ref: str) -> str | None:
    out = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False).strip()
    return out or None


def current_branch(root: Path) -> str | None:
    out = git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
    return out or None


def is_clean(root: Path) -> bool:
    return git(root, "status", "--porcelain", "--untracked-files=no").strip() == ""


def default_branch(root: Path, configured: str | None = None) -> str:
    if configured:
        return configured
    out = git(root, "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD", check=False).strip()
    if out:
        return out.split("/", 1)[1]
    for name in ("main", "master"):
        if rev_parse(root, name) or rev_parse(root, f"origin/{name}"):
            return name
    return current_branch(root) or "main"


def resolve_ref(root: Path, name: str) -> str | None:
    """Local branch first, then ``origin/<name>``."""
    return rev_parse(root, name) or rev_parse(root, f"origin/{name}")


@dataclass
class Commit:
    sha: str
    subject: str
    body: str
    comment_ids: list[str] = field(default_factory=list)

    @property
    def short(self) -> str:
        return self.sha[:7]


def parse_resolves(message: str) -> list[str]:
    ids: list[str] = []
    for m in _RESOLVES.finditer(message):
        for cid in CID_RE.findall(m.group(1)):
            if cid not in ids:
                ids.append(cid)
    return ids


def commits_between(root: Path, base: str, head: str) -> list[Commit]:
    """Non-merge commits in ``base..head``, oldest first."""
    out = git(root, "log", "--reverse", "--no-merges", "--format=%H%x1f%B%x1e", f"{base}..{head}")
    commits = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        sha, _, message = rec.partition("\x1f")
        subject = message.strip().splitlines()[0] if message.strip() else ""
        commits.append(Commit(sha.strip(), subject, message, parse_resolves(message)))
    return commits


def export_tree(root: Path, ref: str, dest: Path) -> None:
    """Extract the tree at ``ref`` into ``dest`` (no .git)."""
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["git", "archive", "--format=tar", ref], cwd=root, capture_output=True)
    if proc.returncode != 0:
        raise GitError(f"git archive {ref} failed: {proc.stderr.decode().strip()}")
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        tar.extractall(dest, filter="data")


def commit_paths(root: Path, paths: list[str], message: str) -> str | None:
    """Stage ``paths`` and commit if anything changed. Returns the new sha or None."""
    for p in paths:
        if (root / p).exists():
            git(root, "add", "-A", "--", p)
    if git(root, "diff", "--cached", "--name-only").strip() == "":
        return None
    git(root, "commit", "-q", "-m", message)
    return rev_parse(root, "HEAD")
