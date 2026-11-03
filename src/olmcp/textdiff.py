"""Small text-diff helpers shared by the redline and the Overleaf thread messages."""

from __future__ import annotations

import difflib
import re


_TOKEN = re.compile(r"\s*(\\[A-Za-z]+|\w+(?:['\u2019-]\w+)*|[^\w\s])")


def _tokens(text: str) -> list[tuple[str, bool]]:
    """Words, LaTeX commands and single punctuation marks, each with 'was there a space before it'."""
    return [(m.group(1), m.start(1) > m.start(0)) for m in _TOKEN.finditer(text)]


def _join(toks: list[tuple[str, bool]]) -> str:
    out = ""
    for t, sp in toks:
        out += (" " if sp and out else "") + t
    return out


def word_diff(old: str, new: str) -> str:
    """Inline word diff: ``kept [-removed-]{+added+} kept``, so a change reads on one line.

    Only words, commands and punctuation are compared (never whitespace), and the original spacing is kept.
    """
    a, b = _tokens(old), _tokens(new)
    out: list[str] = []
    after_piece = False  # the last thing written was a [-..-] / {+..+} marker

    def put(piece: str, space_before: bool, glue: bool = False, equal_tok: str = "") -> None:
        nonlocal after_piece
        word_follows_marker = after_piece and (equal_tok[:1].isalnum() or equal_tok[:1] == "\\")
        if out and (space_before or word_follows_marker) and not glue:
            out.append(" ")
        out.append(piece)
        after_piece = not equal_tok

    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, [t for t, _ in a], [t for t, _ in b], autojunk=False).get_opcodes():
        if op == "equal":
            for t, sp in b[j1:j2]:
                put(t, sp, equal_tok=t)
            continue
        if i2 > i1:
            put("[-" + _join(a[i1:i2]) + "-]", a[i1][1])
        if j2 > j1:
            put("{+" + _join(b[j1:j2]) + "+}", b[j1][1], glue=i2 > i1)
    return "".join(out).strip()


def crop_to_change(diff: str, context: int = 70, limit: int = 260) -> str:
    """One line of a word diff, cut down to the changed words plus a little context."""
    d = " ".join(diff.split())
    starts = [m.start() for m in re.finditer(r"\[-|\{\+", d)]
    if not starts:
        return d[:limit]
    ends = [m.end() for m in re.finditer(r"-\]|\+\}", d)]
    lo = max(0, starts[0] - context)
    hi = min(len(d), (ends[-1] if ends else starts[-1]) + context)
    if lo > 0:
        lo = d.rfind(" ", 0, lo) + 1
    if hi < len(d):
        j = d.find(" ", hi)
        hi = j if j != -1 else len(d)
    s = ("... " if lo > 0 else "") + d[lo:hi] + (" ..." if hi < len(d) else "")
    if len(s) > limit:
        s = s[: limit // 2].rstrip() + " ... " + s[-(limit // 2):].lstrip()
    return s
