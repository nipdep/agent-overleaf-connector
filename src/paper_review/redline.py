"""Generate ``redline.tex`` (next to the real main file): a latexdiff of base vs the agent branch, with a
decision line per agent commit that the human edits in place (inside Overleaf)::

    %% decision[C-0042]: pending      <- change to: accept | reject
    %% reason[C-0042]:                <- optional; sent back to the agent on reject

Changes are attributed to commits heuristically: the head version of each changed
line is looked up with ``git log -S`` (pickaxe) among the branch's commits.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Config, detect_main
from .gitutil import commits_between, export_tree, git, rev_parse
from .store import now

GRAPHICS_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
OTHER_ASSET_EXT = {".bib", ".sty", ".cls", ".bst"}

_INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_DIFF_SPAN = re.compile(r"\\DIF(del|add|mod)begin(?:FL)?\b.*?\\DIF\1end(?:FL)?\b", re.S)
_DECISION = re.compile(r"^[ \t]*%+[ \t]*decision\[([^\]\n]+)\][ \t]*:[ \t]*([A-Za-z-]*)", re.M)
_REASON = re.compile(r"^[ \t]*%+[ \t]*reason\[([^\]\n]+)\][ \t]*:[ \t]*([^\n]*?)[ \t]*$", re.M)
VALID = {"accept", "reject", "pending", "accept-all", "reject-all"}


class RedlineError(RuntimeError):
    pass


# --------------------------------------------------------------------- flatten
def flatten(tree: Path, main: str, _depth: int = 0) -> str:
    """Inline ``\\input``/``\\include`` so one self-contained file can be diffed."""
    path = tree / main
    text = path.read_text(encoding="utf-8", errors="replace")
    if _depth > 10:
        return text

    def inline(line: str) -> str:
        code = line.split("%", 1)[0] if "%" in line and not line.lstrip().startswith("%") else line
        if line.lstrip().startswith("%"):
            return line

        def sub(m: re.Match) -> str:
            name = m.group(1).strip()
            for cand in (name, name + ".tex"):
                if (tree / cand).is_file():
                    return flatten(tree, cand, _depth + 1).rstrip("\n")
            return m.group(0)

        return _INPUT.sub(sub, line) if _INPUT.search(code) else line

    return "\n".join(inline(l) for l in text.split("\n"))


# ------------------------------------------------------- latexdiff text helpers
def _unwrap(s: str, name: str, keep: bool) -> str:
    tok = "\\" + name + "{"
    out, i = [], 0
    while True:
        j = s.find(tok, i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        depth, k = 1, j + len(tok)
        while k < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[k], 0) if s[k - 1] != "\\" else 0
            k += 1
        if keep:
            out.append(s[j + len(tok): k - 1])
        i = k
    return "".join(out)


def view(s: str, side: str) -> str:
    """Reconstruct the ``head`` or ``base`` version of latexdiff-marked text."""
    drop, keep = ("del", "add") if side == "head" else ("add", "del")
    s = re.sub(rf"\\DIF{drop}begin(?:FL)?\b.*?\\DIF{drop}end(?:FL)?\b", "", s, flags=re.S)
    for name in (f"DIF{keep}", f"DIF{keep}FL"):
        s = _unwrap(s, name, True)
    for name in (f"DIF{drop}", f"DIF{drop}FL"):
        s = _unwrap(s, name, False)
    s = re.sub(r"\\DIF(?:add|del|mod)(?:begin|end)(?:FL)?\b ?", "", s)
    return s


@dataclass
class Group:
    start_line: int  # 0-based line index in the redline body
    end_line: int
    text: str
    key: str | None = None


def find_groups(body_lines: list[str]) -> list[Group]:
    text = "\n".join(body_lines)
    spans = [(m.start(), m.end()) for m in _DIFF_SPAN.finditer(text)]
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and not text[merged[-1][1]:s].strip():
            merged[-1][1] = e
        else:
            merged.append([s, e])
    groups = []
    for s, e in merged:
        sl, el = text.count("\n", 0, s), text.count("\n", 0, e)
        groups.append(Group(sl, el, text[s:e]))
    return groups


def _ere_escape(word: str) -> str:
    return "".join("\\" + ch if ch in "\\.[]{}()*+?|^$" else ch for ch in word)


def pickaxe(root: Path, base: str, head: str, snippet: str) -> list[str]:
    """Commits in base..head whose diff touches a line equal to ``snippet``.

    latexdiff pads its markers with spaces, so whitespace is matched loosely.
    """
    words = snippet.split()
    if len(snippet.strip()) < 6 or not words:
        return []
    regex = r"[[:space:]]+".join(_ere_escape(w) for w in words)
    out = git(root, "log", "--format=%H", "-G" + regex, f"{base}..{head}", "--", "*.tex", check=False)
    return out.split()


def snippet_for(group_lines: list[str]) -> str | None:
    for side in ("head", "base"):
        rendered = [l.strip() for l in view("\n".join(group_lines), side).split("\n")]
        rendered = [l for l in rendered if len(l) >= 6 and not l.startswith("%")]
        if rendered:
            return max(rendered, key=len)
    return None


# -------------------------------------------------------------------- decisions
def parse_decisions(text: str) -> dict[str, dict]:
    """``{key: {"decision": ..., "reason": ...}}`` from a redline file."""
    out: dict[str, dict] = {}
    for m in _DECISION.finditer(text):
        key, value = m.group(1).strip(), (m.group(2) or "pending").lower()
        if value not in VALID:
            raise RedlineError(f"decision[{key}]: unknown value {value!r}; use accept, reject or pending")
        out[key] = {"decision": value, "reason": ""}
    for m in _REASON.finditer(text):
        out.setdefault(m.group(1).strip(), {"decision": "pending", "reason": ""})["reason"] = m.group(2)
    return out


# --------------------------------------------------------------------- generate
def _entries(commits) -> list[dict]:
    entries: dict[str, dict] = {}
    for c in commits:
        key = c.comment_ids[0] if c.comment_ids else c.short
        e = entries.setdefault(key, {"key": key, "shas": [], "comment_ids": [], "subject": c.subject})
        e["shas"].append(c.sha)
        for cid in c.comment_ids:
            if cid not in e["comment_ids"]:
                e["comment_ids"].append(cid)
    return list(entries.values())


STUB = r"""%% paper-review: no pending changes.
\documentclass{article}
\begin{document}
No pending agent changes to review.
\end{document}
"""


def generate(cfg: Config, base: str, head: str | None, branch: str | None = None) -> dict:
    """Write redline.tex (beside the main file) and review/redline.json. ``head=None`` writes a stub."""
    cfg.review_path.mkdir(parents=True, exist_ok=True)
    tex_path, json_path = cfg.redline_path, cfg.review_path / "redline.json"
    legacy = cfg.review_path / "redline.tex"  # location used before the redline moved beside the main file
    if legacy.exists() and legacy != tex_path and "paper-review" in legacy.read_text(encoding="utf-8")[:300]:
        if not tex_path.exists():
            tex_path.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")  # keep typed decisions
        legacy.unlink()
    previous = parse_decisions(tex_path.read_text(encoding="utf-8")) if tex_path.exists() else {}
    prev_entries = {}
    if json_path.exists():
        prev_entries = {e["key"]: e for e in json.loads(json_path.read_text(encoding="utf-8")).get("entries", [])}

    base_sha = rev_parse(cfg.root, base)
    head_sha = rev_parse(cfg.root, head) if head else None
    if not base_sha or (head and not head_sha):
        raise RedlineError(f"cannot resolve refs base={base!r} head={head!r}")
    commits = commits_between(cfg.root, base_sha, head_sha) if head_sha else []
    if not commits:
        tex_path.write_text(STUB, encoding="utf-8")
        meta = {"version": 1, "base": base_sha, "head": head_sha, "branch": branch, "entries": [], "generated": now()}
        json_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return meta

    if not shutil.which("latexdiff"):
        raise RedlineError("latexdiff not found; install TeX Live (latexdiff) or use the docker image.")
    main = detect_main(cfg)
    entries = _entries(commits)
    sha_to_key = {sha: e["key"] for e in entries for sha in e["shas"]}

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        export_tree(cfg.root, base_sha, tdp / "base")
        export_tree(cfg.root, head_sha, tdp / "head")
        for side in ("base", "head"):
            if not (tdp / side / main).is_file():
                raise RedlineError(f"main file {main!r} missing at {side}")
        (tdp / "a.tex").write_text(flatten(tdp / "base", main), encoding="utf-8")
        (tdp / "b.tex").write_text(flatten(tdp / "head", main), encoding="utf-8")
        proc = subprocess.run(["latexdiff", "--encoding=utf8", "a.tex", "b.tex"], cwd=tdp, capture_output=True, text=True)
        if proc.returncode != 0 or "\\begin{document}" not in proc.stdout:
            raise RedlineError(f"latexdiff failed: {proc.stderr.strip()[:500]}")
        diff = proc.stdout
        new_assets = _new_assets(tdp / "base", tdp / "head")

    # assets added on the branch don't exist on the default branch yet; copy them
    # next to the redline so it still compiles in Overleaf.
    warnings: list[str] = []
    for rel in new_assets:
        p = Path(rel)
        if p.suffix.lower() in GRAPHICS_EXT:
            dest = cfg.review_path / "assets" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as td2:
                export_tree(cfg.root, head_sha, Path(td2))
                shutil.copyfile(Path(td2) / rel, dest)
            prefix = f"{cfg.review_dir}/assets/"
            for form in (rel, p.with_suffix("").as_posix()):
                diff = diff.replace("{" + form + "}", "{" + prefix + form + "}")
        elif p.suffix.lower() in OTHER_ASSET_EXT:
            warnings.append(f"new file {rel} is not on the default branch; the redline may not compile until it is accepted")

    lines = diff.split("\n")
    body_start = next(i for i, l in enumerate(lines) if l.strip().startswith("\\begin{document}")) + 1
    body = lines[body_start:]
    groups = find_groups(body)
    first_group: dict[str, Group] = {}
    for g in groups:
        snip = snippet_for(body[g.start_line: g.end_line + 1])
        shas = pickaxe(cfg.root, base_sha, head_sha, snip) if snip else []
        keys = [sha_to_key[s] for s in shas if s in sha_to_key]
        g.key = keys[0] if keys else None
        if g.key and g.key not in first_group:
            first_group[g.key] = g

    inserts: dict[int, list[str]] = {}
    placed: set[str] = set()
    for g in groups:
        if g.key is None:
            inserts.setdefault(g.start_line, []).append("%% (change not linked to an agent commit; it cannot be decided separately)")
        elif g is first_group[g.key]:
            e = next(x for x in entries if x["key"] == g.key)
            inserts.setdefault(g.start_line, []).extend(_decision_block(e, previous, prev_entries))
            placed.add(g.key)
        else:
            inserts.setdefault(g.start_line, []).append(f"%% (change continues: {g.key})")
    new_body: list[str] = []
    for i, l in enumerate(body):
        new_body.extend(inserts.get(i, []))
        new_body.append(l)

    unplaced = [e for e in entries if e["key"] not in placed]
    header = _header(entries, base_sha, head_sha, branch, warnings)
    for e in unplaced:
        header.extend(_decision_block(e, previous, prev_entries))
    out = "\n".join(header + [""] + lines[:body_start] + new_body)
    tex_path.write_text(out, encoding="utf-8")
    meta = {"version": 1, "base": base_sha, "head": head_sha, "branch": branch, "entries": entries,
            "generated": now(), "warnings": warnings}
    json_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def _decision_block(entry: dict, previous: dict, prev_entries: dict) -> list[str]:
    key = entry["key"]
    prior = previous.get(key)
    same = prev_entries.get(key, {}).get("shas") == entry["shas"]
    decision = prior["decision"] if prior and same else "pending"
    reason = prior["reason"] if prior and same else ""
    return [
        f"%% ---- paper-review: {key} - {entry['subject']} ----",
        f"%% decision[{key}]: {decision}",
        f"%% reason[{key}]: {reason}",
    ]


def _header(entries, base, head, branch, warnings) -> list[str]:
    h = [
        "%% paper-review redline (generated). Edit ONLY the 'decision[...]' and 'reason[...]' lines.",
        "%% Set a decision to: accept | reject  (leave 'pending' to decide later). Then push to GitHub.",
        f"%% base {base[:7]}  head {head[:7]}" + (f"  branch {branch}" if branch else ""),
        "%% Changes in this round:",
    ]
    h += [f"%%   {e['key']:<8} {e['shas'][0][:7]}  {e['subject']}" for e in entries]
    h += [f"%% WARNING: {w}" for w in warnings]
    return h


def _new_assets(base_tree: Path, head_tree: Path) -> list[str]:
    out = []
    for p in sorted(head_tree.rglob("*")):
        if p.is_file() and p.suffix.lower() in GRAPHICS_EXT | OTHER_ASSET_EXT:
            rel = p.relative_to(head_tree).as_posix()
            if not (base_tree / rel).exists():
                out.append(rel)
    return out
