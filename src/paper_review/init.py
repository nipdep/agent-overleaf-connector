"""``paper-review init``: add the small set of files that wire a repo up.

The repo layout comes from Overleaf, so this only adds files and never moves or
edits existing ones (an existing AGENTS.md is left alone and the protocol is
written to ``review/AGENTS.md`` instead).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from .config import CONFIG_NAME, Config, detect_engine, detect_main
from .gitutil import default_branch

DEFAULT_USES = "nipdep/agent-overleaf-connector/.github/workflows/review.yml@main"


def _template(name: str) -> str:
    return resources.files("paper_review").joinpath("templates", name).read_text(encoding="utf-8")


def _write(path: Path, content: str, actions: list[str], force: bool, label: str) -> bool:
    if path.exists() and not force:
        actions.append(f"skipped {label} (exists)")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    actions.append(f"wrote {label}")
    return True


def init(cfg: Config, *, mode: str = "direct", uses: str = DEFAULT_USES, workflow: bool = True,
         force: bool = False) -> list[str]:
    root = cfg.root
    actions: list[str] = []
    try:
        main = detect_main(cfg)
        engine, how = detect_engine(cfg)
    except FileNotFoundError as exc:
        actions.append(f"warning: {exc}")
        main, engine, how = None, "pdflatex", "default"
    data = {"mode": mode, "engine": engine}
    if main:
        data["main"] = main
    body = (
        "# paper-review configuration (https://github.com/nipdep/agent-overleaf-connector)\n"
        "# mode: direct = agent commits on the current branch; suggest = agent pushes agent/round-N\n"
        "# and you accept/reject changes in review/redline.tex.\n"
        "# engine: Overleaf's compiler setting is not stored in git, so check it matches yours.\n"
    ) + yaml.safe_dump(data, sort_keys=False)
    _write(root / CONFIG_NAME, body, actions, force, CONFIG_NAME)

    if workflow:
        branch = default_branch(root, cfg.default_branch)
        text = _template("workflow.yml").replace("{default_branch}", branch).replace("{uses}", uses)
        _write(root / ".github" / "workflows" / "paper-review.yml", text, actions, force, ".github/workflows/paper-review.yml")

    protocol = _template("AGENTS.md")
    if (root / "AGENTS.md").exists() and not force:
        _write(cfg.review_path / "AGENTS.md", protocol, actions, force, f"{cfg.review_dir}/AGENTS.md (AGENTS.md already exists)")
    else:
        _write(root / "AGENTS.md", protocol, actions, force, "AGENTS.md")
    _write(root / "CLAUDE.md", _template("CLAUDE.md"), actions, force, "CLAUDE.md")
    _write(cfg.review_path / "README.md", _template("review_README.md"), actions, force, f"{cfg.review_dir}/README.md")

    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if f"{cfg.build_dir}/" not in existing.split():
        gi.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + f"{cfg.build_dir}/\n", encoding="utf-8")
        actions.append(f"added {cfg.build_dir}/ to .gitignore")
    return actions
