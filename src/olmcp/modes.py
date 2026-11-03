"""Edit modes: ``direct`` applies an edit to the paper at once; ``suggest`` holds it for review.

The default comes from ``mode:`` in ``.olmcp.yml`` (change it with ``olmcp mode``). A researcher can choose
per comment by starting the comment with a tag: ``[suggest] ...``, ``[direct] ...``, ``suggest: ...`` or
``direct: ...``. A tag is the researcher's choice and is honoured over the default.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import CONFIG_NAME, LEGACY_CONFIG_NAME, Config

MODES = ("direct", "suggest")
_TAG = re.compile(r"^\s*(?:\[(direct|suggest)\]|(direct|suggest)\s*:)", re.I)


def parse_mode_tag(text: str) -> str | None:
    """``"suggest"`` / ``"direct"`` if ``text`` starts with a mode tag, else None."""
    m = _TAG.match(text or "")
    return (m.group(1) or m.group(2)).lower() if m else None


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
