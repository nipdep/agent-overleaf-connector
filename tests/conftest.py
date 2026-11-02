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
