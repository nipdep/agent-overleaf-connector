"""Edit modes and comment tags.

``direct`` applies an edit to the paper at once; ``suggest`` holds it for review. The default comes from
``mode:`` in ``.olmcp.yml`` (change it with ``olmcp mode``).

A researcher can steer a single comment with optional hashtags anywhere in its text:

* ``#suggest`` / ``#direct``: the edit mode for this comment (beats the default and the agent's choice).
* ``#no-agent``: the agent must not work on or reply to this comment.
* ``#agent``: focus. While any open comment carries it, the agent works only on those; the focus ends by
  itself when they are handled, and the agent can still be told to do everything.

Untagged comments behave as before. The older forms ``[suggest]`` / ``direct:`` at the very start of a comment
still work for the mode. ``comment_tags: false`` in the config turns all tag reading off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_NAME, LEGACY_CONFIG_NAME, Config

MODES = ("direct", "suggest")

# A tag is a standalone word: not glued to other text, and not a URL fragment (`page.html#direct`).
_BEFORE = r"(?<![\w#/&=?.-])"
_AFTER = r"(?![\w-])"
_HASH = re.compile(_BEFORE + r"#(no-?agent|agent|suggest|direct)" + _AFTER, re.I)
_LEGACY = re.compile(r"^\s*(?:\[(direct|suggest)\]|(direct|suggest)\s*:)", re.I)


@dataclass(frozen=True)
class Tags:
    agent: bool | None = None  # True: #agent (focus), False: #no-agent (hands off), None: untagged
    mode: str | None = None  # "suggest", "direct" or None


def parse_tags(text: str, enabled: bool = True) -> Tags:
    """The tags in one piece of comment text. Conflicts resolve to the safe side: ``#no-agent`` beats
    ``#agent`` and ``#suggest`` beats ``#direct``."""
    if not enabled or not text:
        return Tags()
    found = {m.group(1).lower().replace("-", "") for m in _HASH.finditer(text)}
    agent = False if "noagent" in found else (True if "agent" in found else None)
    if "suggest" in found:
        mode = "suggest"
    elif "direct" in found:
        mode = "direct"
    else:
        m = _LEGACY.match(text)
        mode = (m.group(1) or m.group(2)).lower() if m else None
    return Tags(agent, mode)


def parse_mode_tag(text: str) -> str | None:
    """``"suggest"`` / ``"direct"`` if ``text`` carries a mode tag, else None."""
    return parse_tags(text).mode


_STRIP = re.compile(_BEFORE + r"#(?:no-?agent|agent|suggest|direct)" + _AFTER, re.I)


def strip_tags(text: str) -> str:
    """The comment without its tags, on one line (for short summaries)."""
    return " ".join(_LEGACY.sub("", _STRIP.sub("", text or ""), count=1).split())


def skip_reasons(comments: list[dict]) -> dict[str, str]:
    """``{comment id: why the agent should leave it alone right now}`` (absent = the agent's to do).

    * ``"no-agent"``: the researcher tagged it ``#no-agent``. Always.
    * ``"focus"``: some open comment is tagged ``#agent`` and this open one is not. Only while such a
      comment is open, so the focus clears itself once the tagged comments are handled.
    """
    focus = any(c["status"] == "open" and c.get("agent") is True for c in comments)
    out: dict[str, str] = {}
    for c in comments:
        if c.get("agent") is False:
            out[c["id"]] = "no-agent"
        elif focus and c["status"] == "open" and c.get("agent") is not True:
            out[c["id"]] = "focus"
    return out


def effective_mode(cfg: Config, comment: dict) -> str:
    """The mode that applies to one comment: its tag if it has one, else the default."""
    return comment.get("mode") or cfg.mode


def write_default_mode(root: Path, value: str) -> Path:
    """Set ``mode:`` in the config file (keeping every other line) and return the file."""
    if value not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, got {value!r}")
    path = root / CONFIG_NAME
    if not path.exists() and (root / LEGACY_CONFIG_NAME).exists():
        path = root / LEGACY_CONFIG_NAME
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if re.search(r"(?m)^mode\s*:", text):
        text = re.sub(r"(?m)^mode\s*:.*$", f"mode: {value}", text, count=1)
    else:
        text += ("" if not text or text.endswith("\n") else "\n") + f"mode: {value}\n"
    path.write_text(text, encoding="utf-8")
    return path
