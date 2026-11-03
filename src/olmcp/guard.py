"""Keep agents away from ``olcli``.

The tool never resolves an Overleaf thread (unless ``auto_resolve_threads``), but an agent with a shell can run
``olcli comments resolve`` itself with the researcher's cookie. These rules deny that where the agent runs;
``olmcp pull`` / ``push`` call ``olcli`` outside the agent and keep working.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from .config import Config

CODEX_RULE_FILE = "olmcp.rules"


def _program(cfg: Config) -> str:
    parts = shlex.split(cfg.olcli or "olcli")
    return Path(parts[0]).name if parts else "olcli"


def claude_rule(cfg: Config) -> str:
    return f"Bash({_program(cfg)}:*)"


def protect_claude(cfg: Config) -> str:
    """Add the deny rule to ``.claude/settings.json``, keeping everything else in it."""
    path = cfg.root / ".claude" / "settings.json"
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"skipped .claude/settings.json (not valid JSON; add deny rule {claude_rule(cfg)!r} yourself)"
    deny = data.setdefault("permissions", {}).setdefault("deny", [])
    rule = claude_rule(cfg)
    if rule in deny:
        return f".claude/settings.json already denies {rule}"
    deny.append(rule)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"added deny rule {rule} to .claude/settings.json (Claude Code cannot run olcli here)"


def codex_rules_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".codex" / "rules" / CODEX_RULE_FILE


def protect_codex(cfg: Config, home: Path | None = None) -> str:
    """Write a Codex execution-policy rule in its own file, leaving ``default.rules`` alone (user-wide)."""
    path = codex_rules_path(home)
    prog = _program(cfg)
    text = (f"# written by olmcp: agents must not run {prog} (it could resolve Overleaf threads)\n"
            f'prefix_rule(pattern=["{prog}"], decision="forbidden")\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return (f"wrote {path} (Codex, all projects). Check it: ask Codex to run '{prog} --help'; "
            "it should be refused. Syntax follows Codex's execpolicy rules; verify it for your version")
