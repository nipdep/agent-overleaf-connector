"""The review loop as plain Python operations, for the MCP server (and tests).

The protocol that AGENTS.md asks an agent to follow is *enforced* here instead of hoped for:
``address_comment`` applies the edits, removes the marker, writes the reply, resolves the
comment and creates the commit with the right ``Resolves:`` trailer in one step, or fails
without changing anything. There is no tool that runs arbitrary commands, and every path is
confined to the paper's repository.
"""

from __future__ import annotations

from pathlib import Path

from . import local
from .apply import ensure_identity
from .build import BuildError, build
from .config import Config, find_root, load_config
from .gitutil import GitError, commit_paths, current_branch, default_branch, git, is_clean
from .markers import remove_marker, scan
from .store import Store

READABLE = {".tex", ".bib", ".sty", ".cls", ".md", ".txt", ".json", ".yml", ".yaml"}
EDITABLE = {".tex", ".bib", ".sty"}
MAX_READ_CHARS = 200_000
MAX_DIFF_CHARS = 8_000


class ToolError(RuntimeError):
    """A refusal or failure that is safe and useful to show the agent."""


class PaperTools:
    def __init__(self, root: Path | None = None):
        self.cfg: Config = load_config(root or find_root())

    # ------------------------------------------------------------------ paths
    def _path(self, rel: str, *, write: bool) -> Path:
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ToolError(f"path must be relative and inside the paper repository: {rel!r}")
        root = self.cfg.root.resolve()
        p = (root / rel).resolve()  # follows symlinks, so a link out of the repo is caught below
        try:
            parts = p.relative_to(root).parts
        except ValueError as exc:
            raise ToolError(f"path escapes the paper repository: {rel!r}") from exc
        blocked = {".git", self.cfg.build_dir} | ({self.cfg.review_dir} if write else set())
        if any(part in blocked for part in parts[:1]) or ".git" in parts:
            raise ToolError(f"{rel!r} is not accessible through these tools")
        allowed = EDITABLE if write else READABLE
        if p.suffix.lower() not in allowed:
            raise ToolError(f"only {', '.join(sorted(allowed))} files can be {'edited' if write else 'read'}: {rel!r}")
        if not p.is_file():
            raise ToolError(f"no such file: {rel!r}")
        return p

    # ------------------------------------------------------------------ sync
    def pull(self) -> dict:
        try:
            return local.pull(self.cfg)
        except (local.LocalError, GitError) as exc:
            raise ToolError(str(exc)) from exc

    def push(self) -> dict:
        try:
            return local.push(self.cfg)
        except (local.LocalError, GitError) as exc:
            raise ToolError(str(exc)) from exc

    # ------------------------------------------------------------------ reading
    def list_comments(self, status: str | None = "open") -> list[dict]:
        out = []
        for c in Store(self.cfg).all():
            if status and c["status"] != status:
                continue
            src = c["anchor"].get("source") or {}
            out.append({
                "id": c["id"], "status": c["status"], "request": c["body"],
                "selected_text": c["anchor"].get("quote") or None,
                "file": src.get("file"), "line": src.get("line"), "page": c["anchor"].get("page"),
                "thread": [{"author": t["author"], "text": t["body"]} for t in c["thread"]],
            })
        return out

    def show_comment(self, comment_id: str, context_lines: int = 6) -> dict:
        try:
            c = Store(self.cfg).get(comment_id)
        except KeyError as exc:
            raise ToolError(str(exc)) from exc
        src = c["anchor"].get("source") or {}
        context, start = "", None
        f = self.cfg.root / src.get("file", "")
        if src.get("file") and f.is_file():
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            n = src.get("line", 1)
            lo, hi = max(0, n - 1 - context_lines), min(len(lines), n + context_lines + 8)
            context, start = "\n".join(lines[lo:hi]), lo + 1
        page = c["anchor"].get("page")
        has_image = bool(page) and (self.cfg.build_path / "pages" / f"p-{page:03d}.png").exists()
        return {
            "id": c["id"], "status": c["status"], "request": c["body"],
            "selected_text": c["anchor"].get("quote") or None,
            "from": (c.get("origin") or {}).get("type"), "file": src.get("file"),
            "line": src.get("line"), "page": page, "page_image_available": has_image,
            "source_context": context, "source_context_first_line": start,
            "thread": [{"author": t["author"], "text": t["body"]} for t in c["thread"]],
        }

    def read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> dict:
        p = self._path(path, write=False)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        lo = max(1, start_line)
        hi = min(len(lines), end_line if end_line else len(lines))
        text = "\n".join(lines[lo - 1: hi])
        truncated = len(text) > MAX_READ_CHARS
        return {"path": path, "start_line": lo, "end_line": hi, "total_lines": len(lines),
                "truncated": truncated, "text": text[:MAX_READ_CHARS]}

    def list_paper_files(self) -> list[str]:
        from .config import iter_tex_files

        return [p.relative_to(self.cfg.root).as_posix() for p in iter_tex_files(self.cfg)]

    # ------------------------------------------------------------------ changing
    def _require_clean(self) -> None:
        if not is_clean(self.cfg.root):
            raise ToolError("the working tree has uncommitted changes; commit or discard them first")

    def _begin_change(self) -> tuple[str, str | None]:
        """Put the repo on the branch the change belongs on; returns (branch, created_branch)."""
        cfg, root = self.cfg, self.cfg.root
        ensure_identity(root)
        self._require_clean()
        default = default_branch(root, cfg.default_branch)
        cur = current_branch(root)
        if cfg.mode == "direct":
            if cur != default:
                git(root, "switch", "-q", default)
            return default, None
        if cur and cur.startswith("agent/round-"):
            return cur, None
        existing = local.agent_branch(cfg)
        if existing:
            git(root, "switch", "-q", existing)
            return existing, None
        name = local.next_round_name(cfg)
        if cur != default:
            git(root, "switch", "-q", default)
        git(root, "switch", "-q", "-c", name)
        return name, name

    def address_comment(self, comment_id: str, edits: list, reply: str,
                        commit_message: str | None = None) -> dict:
        cfg, root = self.cfg, self.cfg.root
        store = Store(cfg)
        try:
            comment = store.get(comment_id)
        except KeyError as exc:
            raise ToolError(str(exc)) from exc
        if comment["status"] in {"resolved", "wontfix"}:
            raise ToolError(f"{comment_id} is already {comment['status']}")
        if not (reply or "").strip():
            raise ToolError("a reply is required: say what you changed and why")
        edits = [e if isinstance(e, dict) else e.model_dump() for e in (edits or [])]
        if not edits:
            raise ToolError("at least one edit is required; to ask the researcher a question use reply_to_comment")

        default = default_branch(root, cfg.default_branch)
        branch, created = self._begin_change()
        try:
            new_texts: dict[Path, str] = {}
            for e in edits:
                old, new = e.get("old", ""), e.get("new", "")
                if not old or old == new:
                    raise ToolError("each edit needs a non-empty 'old' text that differs from 'new'")
                p = self._path(e.get("file", ""), write=True)
                text = new_texts.get(p)
                if text is None:
                    text = p.read_text(encoding="utf-8")
                n = text.count(old)
                if n != 1:
                    raise ToolError(f"{e['file']}: 'old' must match exactly once in the file, found {n}. "
                                    f"Read the file again and copy a longer, unique passage.")
                new_texts[p] = text.replace(old, new, 1)

            origin = comment.get("origin") or {}
            if origin.get("type") == "marker":  # the request is handled: drop its marker block
                for m in scan(cfg):
                    if m.external_id == origin.get("external_id"):
                        mp = (root / m.file).resolve()
                        text = new_texts.get(mp) or mp.read_text(encoding="utf-8")
                        new_texts[mp], _ = remove_marker(text, m.file, m.external_id, cfg.marker)
                        break

            for p, text in new_texts.items():
                p.write_text(text, encoding="utf-8")
            store.reply(comment_id, "agent", reply.strip())
            status = "resolved" if cfg.mode == "direct" else "addressed"
            store.set_status(comment_id, status, by="agent", note=reply.strip()[:300])

            message = f"{(commit_message or f'Address {comment_id}').strip()}\n\nResolves: {comment_id}\n"
            paths = [p.relative_to(root.resolve()).as_posix() for p in new_texts]
            paths.append(f"{cfg.review_dir}/comments/{comment_id}.json")
            sha = commit_paths(root, paths, message)
            if not sha:
                raise ToolError("the edits produced no change")
        except Exception:
            git(root, "reset", "-q", "--hard", "HEAD")  # nothing half-applied
            if created:
                git(root, "switch", "-q", default)
                git(root, "branch", "-D", created, check=False)
            raise

        diff = git(root, "show", "--format=", "-U2", sha)
        return {
            "comment_id": comment_id, "status": status, "mode": cfg.mode, "branch": branch,
            "commit": sha[:10], "files": [p for p in paths if not p.endswith(".json")],
            "diff": diff[:MAX_DIFF_CHARS] + ("\n... (truncated)" if len(diff) > MAX_DIFF_CHARS else ""),
            "next": "Address the remaining open comments, then call push.",
        }

    def reply_to_comment(self, comment_id: str, text: str) -> dict:
        """Reply without changing the paper (a question or an explanation). The comment stays open."""
        cfg, root = self.cfg, self.cfg.root
        if not (text or "").strip():
            raise ToolError("reply text is empty")
        ensure_identity(root)
        self._require_clean()
        default = default_branch(root, cfg.default_branch)
        if current_branch(root) != default:
            git(root, "switch", "-q", default)
        store = Store(cfg)
        try:
            store.reply(comment_id, "agent", text.strip())
        except KeyError as exc:
            raise ToolError(str(exc)) from exc
        commit_paths(root, [f"{cfg.review_dir}/comments/{comment_id}.json"], f"olmcp: reply on {comment_id}")
        return {"comment_id": comment_id, "status": store.get(comment_id)["status"], "branch": default,
                "next": "The reply is published by push."}

    # ------------------------------------------------------------------ rendering (optional)
    def build(self) -> dict:
        try:
            return build(self.cfg)
        except BuildError as exc:
            raise ToolError(f"rendering is unavailable: {exc}") from exc
        except FileNotFoundError as exc:
            raise ToolError(str(exc)) from exc

    def page_image_path(self, page: int) -> Path:
        p = self.cfg.build_path / "pages" / f"p-{page:03d}.png"
        if not p.exists():
            raise ToolError("no rendered page; call build first (needs TeX installed) or skip visual checks")
        return p
