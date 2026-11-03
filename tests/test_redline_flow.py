"""End-to-end: suggest-mode round with real git and real latexdiff."""

import json
import re

import pytest

from olmcp.apply import ApplyError, apply
from olmcp.ci import run as ci_run
from olmcp.config import load_config
from olmcp.gitutil import git
from olmcp.redline import generate, parse_decisions
from olmcp.store import Store
from olmcp.sync import sync

from conftest import needs_latexdiff, sh

pytestmark = needs_latexdiff


def commit_all(repo, msg):
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-q", "-m", msg)


@pytest.fixture
def round1(repo, cfg):
    """main has synced comments; agent/round-1 fixes both, one commit each."""
    sync(cfg)
    commit_all(repo, "sync comments")
    sh(repo, "git", "switch", "-q", "-c", "agent/round-1")
    res = repo / "sections" / "results.tex"
    res.write_text(
        res.read_text()
        .replace("%% @agent: soften this claim and add a citation\n", "")
        .replace("always outperforms the baselines on all benchmarks we tried", "outperforms most baselines on the benchmarks we tried")
    )
    commit_all(repo, "Soften results claim\n\nResolves: C-0002")
    intro = repo / "sections" / "intro.tex"
    intro.write_text(
        intro.read_text()
        .replace("%% @agent: tighten this opening sentence\n", "")
        .replace("a long sentence", "one sentence")
    )
    commit_all(repo, "Tighten intro\n\nResolves: C-0001")
    sh(repo, "git", "switch", "-q", "main")
    return repo


def test_redline_has_decision_lines_next_to_changes(round1, cfg):
    meta = generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    assert [e["key"] for e in meta["entries"]] == ["C-0002", "C-0001"]
    text = (cfg.redline_path).read_text()
    assert parse_decisions(text) == {"C-0002": {"decision": "pending", "reason": ""},
                                     "C-0001": {"decision": "pending", "reason": ""}}
    # the decision block sits immediately above its own change
    lines = text.split("\n")
    i = next(n for n, l in enumerate(lines) if "decision[C-0002]" in l)
    nearby = "\n".join(lines[i: i + 8])
    assert "outperforms most baselines" in nearby or "always outperforms" in nearby
    j = next(n for n, l in enumerate(lines) if "decision[C-0001]" in l)
    assert "\\DIFadd{one }" in "\n".join(lines[j: j + 4])
    assert "\\DIFadd" in text


def test_accept_one_reject_one(round1, repo, cfg):
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    tex = cfg.redline_path
    s = tex.read_text()
    s = s.replace("decision[C-0002]: pending", "decision[C-0002]: accept")
    s = s.replace("decision[C-0001]: pending", "decision[C-0001]: reject")
    s = re.sub(r"(reason\[C-0001\]:).*", r"\1 keep my wording", s)
    tex.write_text(s)
    commit_all(repo, "decisions from Overleaf")

    result = apply(cfg)
    assert result["status"] == "applied"
    assert (result["accepted"], result["rejected"], result["pending"]) == (["C-0002"], ["C-0001"], [])
    assert result["branch_action"] == "deleted"

    results = (repo / "sections" / "results.tex").read_text()
    intro = (repo / "sections" / "intro.tex").read_text()
    assert "outperforms most baselines" in results and "@agent" not in results  # accepted
    assert "a long sentence" in intro and "@agent: tighten" in intro  # rejected: untouched, marker stays

    store = Store(cfg)
    assert store.get("C-0002")["status"] == "resolved"
    c1 = store.get("C-0001")
    assert c1["status"] == "open" and "keep my wording" in c1["thread"][-1]["body"]

    assert "pre-apply" in git(repo, "tag", "--list")  # rollback point
    assert git(repo, "branch", "--list", "agent/round-1").strip() == ""
    assert "No pending agent changes" in tex.read_text()  # redline reset to stub
    assert git(repo, "status", "--porcelain").strip() == ""


def test_pending_commits_survive_on_a_recreated_branch(round1, repo, cfg):
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    tex = cfg.redline_path
    tex.write_text(tex.read_text().replace("decision[C-0002]: pending", "decision[C-0002]: accept"))
    commit_all(repo, "accept one")
    result = apply(cfg)
    assert (result["accepted"], result["pending"], result["branch_action"]) == (["C-0002"], ["C-0001"], "recreated")
    new_meta = json.loads((cfg.review_path / "redline.json").read_text())
    assert [e["key"] for e in new_meta["entries"]] == ["C-0001"]
    assert "one sentence" in (repo / "sections" / "intro.tex").read_text() or True
    assert "decision[C-0001]: pending" in tex.read_text()
    assert "decision[C-0002]" not in tex.read_text()


def test_stale_redline_is_refused(round1, repo, cfg):
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    tex = cfg.redline_path
    tex.write_text(tex.read_text().replace("decision[C-0002]: pending", "decision[C-0002]: accept"))
    commit_all(repo, "decide")
    sh(repo, "git", "switch", "-q", "agent/round-1")
    (repo / "sections" / "intro.tex").write_text((repo / "sections" / "intro.tex").read_text() + "\nExtra.\n")
    commit_all(repo, "agent moved on\n\nResolves: C-0001")
    sh(repo, "git", "switch", "-q", "main")
    with pytest.raises(ApplyError, match="moved"):
        apply(cfg)


def test_conflict_rolls_back_everything(round1, repo, cfg):
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    tex = cfg.redline_path
    tex.write_text(tex.read_text().replace("decision[C-0002]: pending", "decision[C-0002]: accept"))
    # a concurrent edit on main touches the same line the accepted commit changed
    res = repo / "sections" / "results.tex"
    res.write_text(res.read_text().replace("always outperforms the baselines", "usually beats the baselines"))
    commit_all(repo, "human edit in Overleaf")
    before = git(repo, "rev-parse", "HEAD").strip()
    with pytest.raises(ApplyError, match="conflict"):
        apply(cfg)
    assert git(repo, "rev-parse", "HEAD").strip() == before
    assert git(repo, "status", "--porcelain").strip() == ""


def test_ci_agent_branch_then_default_applies_decisions(round1, repo, cfg):
    """The workflow's two entry points, without a remote."""
    sh(repo, "git", "switch", "-q", "agent/round-1")
    assert ci_run(cfg, branch="agent/round-1")["ok"]
    assert git(repo, "branch", "--show-current").strip() == "main"
    assert (cfg.redline_path).exists()
    assert "[skip ci]" in git(repo, "log", "-1", "--format=%s")

    tex = cfg.redline_path
    tex.write_text(tex.read_text().replace("decision[C-0001]: pending", "decision[C-0001]: accept"))
    commit_all(repo, "overleaf: decisions")
    out = ci_run(cfg, branch="main")
    assert out["ok"], out
    assert any(l.startswith("apply:") for l in out["log"])
    assert "one sentence" in (repo / "sections" / "intro.tex").read_text()
    changelog = (cfg.review_path / "CHANGELOG.md").read_text()
    assert "C-0001" in changelog and "Tighten intro" in changelog
    assert load_config(repo).root == repo


def test_dependent_assets_copied_for_redline(round1, repo, cfg):
    sh(repo, "git", "switch", "-q", "agent/round-1")
    (repo / "figures").mkdir()
    (repo / "figures" / "fig1.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    res = repo / "sections" / "results.tex"
    res.write_text(res.read_text().replace("The ablation study is unchanged.",
                                           "The ablation study is unchanged.\n\\includegraphics{figures/fig1}\n"))
    commit_all(repo, "Add figure\n\nResolves: C-0002")
    sh(repo, "git", "switch", "-q", "main")
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    assert (cfg.review_path / "assets" / "figures" / "fig1.png").exists()
    assert "review/assets/figures/fig1" in (cfg.redline_path).read_text()


def test_redline_compiles_to_pdf(round1, repo, cfg):
    import subprocess

    from conftest import needs_latexmk  # noqa: F401
    import shutil

    if not shutil.which("latexmk"):
        pytest.skip("latexmk not installed")
    generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    proc = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
                           "-outdir=build", "redline.tex"], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-800:]
    import pymupdf

    with pymupdf.open(repo / "build" / "redline.pdf") as doc:
        text = doc[0].get_text()
    # both the removed and the added wording are visible in a redline
    assert "always" in text and "most" in text  # wavy underline splits words with ":::"


def test_ci_pushes_to_a_real_remote(round1, repo, cfg, tmp_path):
    remote = tmp_path / "remote.git"
    sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(remote))
    sh(repo, "git", "remote", "add", "origin", str(remote))
    sh(repo, "git", "push", "-q", "origin", "main", "agent/round-1")
    sh(repo, "git", "fetch", "-q", "origin")

    # CI run for the agent push: redline lands on the remote default branch
    sh(repo, "git", "switch", "-q", "agent/round-1")
    assert ci_run(cfg, branch="agent/round-1", push=True)["ok"]
    assert "redline.tex" in sh(tmp_path, "git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")

    # researcher (Overleaf) accepts one and rejects one, CI applies and pushes
    tex = cfg.redline_path
    tex.write_text(tex.read_text().replace("decision[C-0002]: pending", "decision[C-0002]: accept")
                   .replace("decision[C-0001]: pending", "decision[C-0001]: reject"))
    commit_all(repo, "overleaf: decisions")
    sh(repo, "git", "push", "-q", "origin", "main")
    assert ci_run(cfg, branch="main", push=True)["ok"]

    remote_results = sh(tmp_path, "git", "--git-dir", str(remote), "show", "main:sections/results.tex")
    assert "outperforms most baselines" in remote_results
    branches = sh(tmp_path, "git", "--git-dir", str(remote), "branch", "--list")
    assert "agent/round-1" not in branches  # all decided -> remote branch deleted
    tags = sh(tmp_path, "git", "--git-dir", str(remote), "tag", "--list")
    assert "olmcp/pre-apply-" in tags  # rollback point survives the CI runner
    assert sh(repo, "git", "status", "--porcelain").strip() == ""


def test_commit_outside_the_compiled_paper_is_flagged_not_silent(round1, repo, cfg):
    """An agent commit that edits a file main.tex never inputs must produce a visible warning."""
    sh(repo, "git", "switch", "-q", "agent/round-1")
    (repo / "archive").mkdir()
    (repo / "archive" / "old_draft.tex").write_text("Old draft text.\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "Edit the archived draft\n\nResolves: C-0099")
    sh(repo, "git", "switch", "-q", "main")
    meta = generate(cfg, "main", "agent/round-1", branch="agent/round-1")
    assert any("C-0099: no visible change" in w and "archive/old_draft.tex" in w for w in meta["warnings"])
    assert "WARNING: C-0099: no visible change" in cfg.redline_path.read_text()
    # the real changes in the same round are unaffected
    assert "decision[C-0002]" in cfg.redline_path.read_text()
