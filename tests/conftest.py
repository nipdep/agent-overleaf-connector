import shutil
import subprocess
from pathlib import Path

import pytest

from paper_review.cli import main as cli_main
from paper_review.config import load_config

MAIN = r"""\documentclass{article}
\begin{document}
\input{sections/intro}
\input{sections/results}
\end{document}
"""
INTRO = """\\section{Intro}
%% @agent: tighten this opening sentence
We study the problem of reviewing papers with agents in a long sentence.

Another intro paragraph that stays as it is.
"""
RESULTS = """\\section{Results}
%% @agent: soften this claim and add a citation
Our method always outperforms the baselines on all benchmarks we tried.

The ablation study is unchanged.
"""

needs_latexdiff = pytest.mark.skipif(not shutil.which("latexdiff"), reason="latexdiff not installed")
needs_latexmk = pytest.mark.skipif(not shutil.which("latexmk"), reason="latexmk not installed")


def sh(root: Path, *args: str) -> str:
    return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "paper"
    (root / "sections").mkdir(parents=True)
    (root / "main.tex").write_text(MAIN)
    (root / "sections" / "intro.tex").write_text(INTRO)
    (root / "sections" / "results.tex").write_text(RESULTS)
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.com")
    sh(root, "git", "config", "user.name", "Tester")
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", "initial paper")
    return root


@pytest.fixture
def cli(repo):
    def run(*args: str) -> int:
        return cli_main(["--root", str(repo), *args])

    return run


@pytest.fixture
def cfg(repo):
    return load_config(repo)


@pytest.fixture
def world(repo, tmp_path):
    """repo = the agent machine's clone; ``overleaf`` = bare remote; ``user`` = Overleaf editing."""
    sh(repo, "git", "branch", "-M", "master")
    bare = tmp_path / "overleaf.git"
    sh(tmp_path, "git", "init", "-q", "--bare", "-b", "master", str(bare))
    sh(repo, "git", "remote", "add", "origin", str(bare))
    sh(repo, "git", "push", "-q", "-u", "origin", "master")
    user = tmp_path / "user"
    sh(tmp_path, "git", "clone", "-q", str(bare), str(user))
    sh(user, "git", "config", "user.email", "researcher@example.com")
    sh(user, "git", "config", "user.name", "Researcher")

    class W:
        pass

    w = W()
    w.repo, w.bare, w.user, w.cfg = repo, bare, user, load_config(repo)

    def user_edit(path, old, new, msg):
        sh(user, "git", "pull", "-q", "--rebase", "origin", "master")
        p = user / path
        p.write_text(p.read_text().replace(old, new))
        sh(user, "git", "commit", "-qam", msg)
        sh(user, "git", "push", "-q", "origin", "master")

    def remote_file(path):
        return sh(tmp_path, "git", "--git-dir", str(bare), "show", f"master:{path}")

    w.user_edit, w.remote_file = user_edit, remote_file
    return w


def agent_commit(repo, path, old, new, msg):
    p = repo / path
    p.write_text(p.read_text().replace(old, new))
    sh(repo, "git", "commit", "-qam", msg)
