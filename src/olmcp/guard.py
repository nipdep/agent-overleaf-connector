"""Keep agents away from the Overleaf client (``olmcp-overleaf``, and the old ``olcli`` if it is installed).

The tool never resolves an Overleaf thread, and ``olmcp-overleaf`` has no resolve command, but the old ``olcli``
does, and any program holding the researcher's cookie could. These rules deny the client commands where the agent
runs; ``olmcp pull`` / ``push`` call the client outside the agent and keep working.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from .config import Config

CODEX_RULE_FILE = "olmcp.rules"


def _programs(cfg: Config) -> list[str]:
    parts = shlex.split(cfg.overleaf_client or "olmcp-overleaf")
    names = [Path(parts[0]).name] if parts else []
    return list(dict.fromkeys(names + ["olmcp-overleaf", "olcli"]))


def claude_rule(cfg: Config) -> str:
    return f"Bash({_programs(cfg)[0]}:*)"


def claude_rules(cfg: Config) -> list[str]:
    return [f"Bash({p}:*)" for p in _programs(cfg)]


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
    missing = [r for r in claude_rules(cfg) if r not in deny]
    if not missing:
        return ".claude/settings.json already denies the Overleaf client"
    deny.extend(missing)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"added deny rules {', '.join(missing)} to .claude/settings.json (Claude Code cannot run the client here)"


def codex_rules_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".codex" / "rules" / CODEX_RULE_FILE


def protect_codex(cfg: Config, home: Path | None = None) -> str:
    """Write a Codex execution-policy rule in its own file, leaving ``default.rules`` alone (user-wide)."""
    path = codex_rules_path(home)
    progs = _programs(cfg)
    text = "# written by olmcp: agents must not run the Overleaf client directly\n" + "".join(
        f'prefix_rule(pattern=["{p}"], decision="forbidden")\n' for p in progs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return (f"wrote {path} (Codex, all projects). Check it: ask Codex to run '{progs[0]} --help'; "
            "it should be refused. Syntax follows Codex's execpolicy rules; verify it for your version")
