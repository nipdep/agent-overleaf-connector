"""Parse ``%% @agent: ...`` marker comments out of .tex files.

A marker is plain text in the source, so it works inside Overleaf with no tooling
and survives GitHub sync. It applies to the paragraph that follows it::

    %% @agent: soften this claim and add a citation
    %% | (continuation lines start with "%% |")
    Our method always outperforms the baselines.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import Config, iter_tex_files


@dataclass
class Marker:
    file: str  # relative to repo root, posix
    line: int  # 1-based line of the marker
    end_line: int  # last line of the marker block
    text: str
    quote: str  # raw LaTeX of the paragraph that follows

    @property
    def external_id(self) -> str:
        """Stable across line moves: depends on file and text only."""
        return hashlib.sha1(f"{self.file}\n{self.text}".encode()).hexdigest()[:12]


def _patterns(tag: str):
    start = re.compile(r"^\s*%+\s*@" + re.escape(tag) + r"\s*:\s*(.*?)\s*$")
    cont = re.compile(r"^\s*%+\s*\|\s?(.*?)\s*$")
    return start, cont


def parse_markers(text: str, rel: str, tag: str = "agent", max_quote: int = 600) -> list[Marker]:
    start, cont = _patterns(tag)
    lines = text.splitlines()
    out: list[Marker] = []
    i = 0
    while i < len(lines):
        m = start.match(lines[i])
        if not m:
            i += 1
            continue
        parts = [m.group(1)]
        j = i + 1
        while j < len(lines) and (c := cont.match(lines[j])):
            parts.append(c.group(1))
            j += 1
        # the paragraph that follows: skip blank and comment-only lines, stop at blank
        quote_lines: list[str] = []
        k = j
        while k < len(lines) and not lines[k].strip():
            k += 1
        while k < len(lines) and lines[k].strip():
            if not lines[k].lstrip().startswith("%"):
                quote_lines.append(lines[k])
            k += 1
        quote = "\n".join(quote_lines)[:max_quote]
        out.append(Marker(rel, i + 1, j, " ".join(p for p in parts if p).strip(), quote))
        i = j
    return out


def scan(cfg: Config) -> list[Marker]:
    found: list[Marker] = []
    for p in iter_tex_files(cfg):
        rel = p.relative_to(cfg.root).as_posix()
        found.extend(parse_markers(p.read_text(encoding="utf-8", errors="replace"), rel, cfg.marker))
    return found


def remove_marker(text: str, rel: str, external_id: str, tag: str = "agent") -> tuple[str, bool]:
    """Remove the marker block whose ``external_id`` matches; returns ``(new_text, removed)``."""
    for m in parse_markers(text, rel, tag):
        if m.external_id == external_id:
            lines = text.splitlines(keepends=True)
            del lines[m.line - 1: m.end_line]
            return "".join(lines), True
    return text, False


def strip_marker_lines(text: str, tag: str = "agent") -> str:
    """Remove marker blocks from source (used by the agent when it resolves one)."""
    start, cont = _patterns(tag)
    lines = text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        if start.match(lines[i].rstrip("\n")):
            i += 1
            while i < len(lines) and cont.match(lines[i].rstrip("\n")):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)
