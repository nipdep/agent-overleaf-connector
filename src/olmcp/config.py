"""Configuration loading and layout detection.

The repository layout is dictated by Overleaf, so nothing here assumes a shape:
the main file and engine are detected, and everything can be overridden in
``.olmcp.yml``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_NAME = ".olmcp.yml"
LEGACY_CONFIG_NAME = ".paper-review.yml"  # the tool's first name; still read, `init` migrates it
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

_DOCCLASS = re.compile(r"^[^%\n]*\\documentclass", re.M)
_ENGINE_MAGIC = re.compile(r"^\s*%\s*!TEX\s+(?:TS-)?program\s*=\s*(\w+)", re.I | re.M)
ENGINES = {"pdflatex", "xelatex", "lualatex"}


@dataclass
class Config:
    root: Path
    main: str | None = None  # path of the main .tex file, relative to root
    engine: str | None = None  # pdflatex | xelatex | lualatex
    mode: str = "direct"  # direct | suggest
    review_dir: str = "review"
    build_dir: str = "build"
    default_branch: str | None = None
    overleaf_project: str | None = None  # override; normally read from the git remote URL
    overleaf_comments: bool = True  # set false to turn native Overleaf comments off
    comment_tags: bool = True  # read #agent / #no-agent / #suggest / #direct in comments; false = plain text
    auto_resolve_threads: bool = False  # true: close an Overleaf thread when its change is applied (default: only you do)
    olcli: str = "olcli"  # command used to reach Overleaf's comment API
    remote: str = "origin"  # git remote used by `pull` / `push` (e.g. Overleaf's git.overleaf.com)
    remote_branch: str | None = None  # branch on that remote (Overleaf: master or main); default: the default branch
    marker: str = "agent"  # comment marker word: ``%% @agent: ...``
    page_dpi: int = 110
    extra: dict = field(default_factory=dict)

    @property
    def review_path(self) -> Path:
        return self.root / self.review_dir

    @property
    def build_path(self) -> Path:
        return self.root / self.build_dir

    @property
    def comments_path(self) -> Path:
        return self.review_path / "comments"

    @property
    def redline_path(self) -> Path:
        """The redline main file lives in the same folder as the real main file, so Overleaf
        resolves its relative paths exactly as it does for the paper itself."""
        try:
            main = self.main or detect_main(self)
        except FileNotFoundError:
            main = "main.tex"
        return self.root / Path(main).parent / "redline.tex"

    @property
    def redline_rel(self) -> str:
        return self.redline_path.relative_to(self.root).as_posix()

    @property
    def redline_files(self) -> list[str]:
        """Everything the redline step writes, for committing. Includes the pre-v0.2 location
        (``review/redline.tex``) so a stale copy is removed when the new one is written."""
        return [self.redline_rel, f"{self.review_dir}/redline.json", f"{self.review_dir}/assets",
                f"{self.review_dir}/redline.tex"]


def find_root(start: Path | None = None) -> Path:
    """Repository root: nearest ancestor holding a config file or ``.git``."""
    start = (start or Path.cwd()).resolve()
    for d in [start, *start.parents]:
        if (d / CONFIG_NAME).exists() or (d / LEGACY_CONFIG_NAME).exists() or (d / ".git").exists():
            return d
    return start


def load_config(root: Path) -> Config:
    root = root.resolve()
    cfg = Config(root=root)
    path = root / CONFIG_NAME
    if not path.exists() and (root / LEGACY_CONFIG_NAME).exists():
        path = root / LEGACY_CONFIG_NAME
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, value in data.items():
            if hasattr(cfg, key) and key not in {"root", "extra"}:
                setattr(cfg, key, value)
            else:
                cfg.extra[key] = value
    if cfg.mode not in {"direct", "suggest", "review"}:
        raise ValueError(f"mode must be 'direct', 'suggest' or 'review', got {cfg.mode!r}")
    return cfg


def _is_generated_redline(p: Path) -> bool:
    if p.name != "redline.tex":
        return False
    try:
        head = p.read_text(encoding="utf-8", errors="replace")[:300]
        return "olmcp" in head or "paper-review" in head  # files generated before the rename
    except OSError:
        return False


def iter_tex_files(cfg: Config):
    """All .tex files in the project, skipping hidden dirs, build and review dirs and the
    generated redline (it is not the paper and its markup must not be scanned)."""
    skip = SKIP_DIRS | {cfg.build_dir, cfg.review_dir}
    for p in sorted(cfg.root.rglob("*.tex")):
        rel = p.relative_to(cfg.root)
        if any(part in skip or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if _is_generated_redline(p):
            continue
        yield p


def detect_main(cfg: Config) -> str:
    """Main file: configured, else the only/first file with ``\\documentclass``."""
    if cfg.main:
        return cfg.main
    candidates = []
    for p in iter_tex_files(cfg):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _DOCCLASS.search(text):
            candidates.append(p.relative_to(cfg.root).as_posix())
    if not candidates:
        raise FileNotFoundError("no .tex file containing \\documentclass found; set 'main' in " + CONFIG_NAME)
    for name in candidates:
        if Path(name).name in {"main.tex", "paper.tex"}:
            return name
    return sorted(candidates, key=lambda n: (n.count("/"), n))[0]


def detect_engine(cfg: Config, main_text: str | None = None) -> tuple[str, str]:
    """Return ``(engine, how)``; ``how`` says where the answer came from."""
    if cfg.engine:
        return cfg.engine, "config"
    if main_text is None:
        main_text = (cfg.root / detect_main(cfg)).read_text(encoding="utf-8", errors="replace")
    m = _ENGINE_MAGIC.search(main_text[:4000])
    if m and m.group(1).lower() in ENGINES:
        return m.group(1).lower(), "magic comment"
    rc = cfg.root / "latexmkrc"
    if not rc.exists():
        rc = cfg.root / ".latexmkrc"
    if rc.exists():
        body = rc.read_text(encoding="utf-8", errors="replace")
        for eng in ("xelatex", "lualatex"):
            if eng in body:
                return eng, "latexmkrc"
    return "pdflatex", "default (Overleaf's compiler setting is not stored in git)"
