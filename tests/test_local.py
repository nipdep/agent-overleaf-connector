"""Local-first mode (pull / push, no CI) against a bare repo that behaves like
Overleaf's Git server: one branch called ``master``. A second clone plays the
researcher editing in Overleaf."""

import json

import pytest

from paper_review.config import load_config
from paper_review.gitutil import git
from paper_review.local import LocalError, agent_branch, pull, push
from paper_review.store import Store

from conftest import agent_commit, needs_latexdiff, sh


def test_pull_reports_what_the_researcher_did(world):
    w = world
    w.user_edit("sections/intro.tex", "%% @agent: tighten this opening sentence\n", "", "researcher removes marker")
    out = pull(w.cfg)
    assert out["fetched_commits"] == 1 and out["files"] == ["sections/intro.tex"]
    # the intro marker was sync'd for the first time AND already removed -> never created; the
    # results marker is new
    assert out["comments"]["new"] == ["C-0001"]
    assert [o["body"] for o in out["open"]] == ["soften this claim and add a citation"]
    assert sh(w.repo, "git", "status", "--porcelain").strip() == ""

    # researcher removes the remaining marker in Overleaf -> reported as removed by researcher
    w.user_edit("sections/results.tex", "%% @agent: soften this claim and add a citation\n", "", "removes marker")
    out = pull(w.cfg)
    assert out["comments"]["removed_by_researcher"] == ["C-0001"] and out["open"] == []


def test_pull_with_nothing_new_is_quiet(world):
    pull(world.cfg)
    out = pull(world.cfg)
    assert out["fetched_commits"] == 0 and not any(out["comments"].values()) and out["warnings"] == []


def test_pull_refuses_dirty_tree(world):
    (world.repo / "sections" / "intro.tex").write_text("dirty\n")
    with pytest.raises(LocalError, match="uncommitted"):
        pull(world.cfg)


def test_pull_conflict_with_unpushed_local_commit_changes_nothing(world):
    w = world
    agent_commit(w.repo, "sections/results.tex", "always outperforms", "never loses to", "local edit on master")
    w.user_edit("sections/results.tex", "always outperforms", "usually beats", "researcher edit same line")
    before = git(w.repo, "rev-parse", "HEAD").strip()
    with pytest.raises(LocalError, match="conflict"):
        pull(w.cfg)
    assert git(w.repo, "rev-parse", "HEAD").strip() == before
    assert sh(w.repo, "git", "status", "--porcelain").strip() == ""
    assert not (w.repo / ".git" / "rebase-merge").exists()


def test_push_publishes_and_retries_when_researcher_pushed_meanwhile(world):
    w = world
    pull(w.cfg)
    agent_commit(w.repo, "sections/results.tex", "always outperforms", "outperforms", "agent edit")
    w.user_edit("sections/intro.tex", "Another intro paragraph", "A second intro paragraph", "researcher edit")
    out = push(w.cfg)
    assert out["remote"] == "origin/master"
    assert "outperforms the baselines" in w.remote_file("sections/results.tex")
    assert "A second intro paragraph" in w.remote_file("sections/intro.tex")  # kept, not overwritten
    # linear history: no merge commits were created
    assert sh(w.repo, "git", "rev-list", "--merges", "--count", "HEAD").strip() == "0"


@needs_latexdiff
def test_full_local_round_without_ci_or_polling(world):
    w, repo = world, world.repo
    pull(w.cfg)  # picks up the two markers -> C-0001 (intro), C-0002 (results)
    assert [c["id"] for c in Store(w.cfg).all()] == ["C-0001", "C-0002"]

    # --- agent task (suggest mode): one commit per comment on a local agent branch
    sh(repo, "git", "switch", "-q", "-c", "agent/round-1")
    agent_commit(repo, "sections/results.tex",
                 "%% @agent: soften this claim and add a citation\nOur method always outperforms the baselines on all benchmarks we tried.",
                 "Our method outperforms most baselines on all benchmarks we tried.", "Soften claim\n\nResolves: C-0002")
    agent_commit(repo, "sections/intro.tex",
                 "%% @agent: tighten this opening sentence\nWe study the problem of reviewing papers with agents in a long sentence.",
                 "We study reviewing papers with agents.", "Tighten intro\n\nResolves: C-0001")
    sh(repo, "git", "switch", "-q", "master")
    out = push(w.cfg)
    assert out["redline"].startswith("2 change(s)")

    # the agent branch never leaves the machine; only master (with the redline) is published
    assert "agent/round-1" not in sh(w.bare.parent, "git", "--git-dir", str(w.bare), "branch", "--list")
    redline = w.remote_file("redline.tex")
    assert "decision[C-0001]: pending" in redline and "decision[C-0002]: pending" in redline
    assert "outperforms the baselines" in w.remote_file("sections/results.tex")  # not applied yet

    # --- researcher in Overleaf: accept C-0002, reject C-0001 with a reason
    sh(w.user, "git", "pull", "-q", "--rebase", "origin", "master")
    tex = w.user / "redline.tex"
    s = tex.read_text().replace("decision[C-0002]: pending", "decision[C-0002]: accept") \
        .replace("decision[C-0001]: pending", "decision[C-0001]: reject") \
        .replace("reason[C-0001]: ", "reason[C-0001]: keep my wording", 1)
    tex.write_text(s)
    sh(w.user, "git", "commit", "-qam", "decisions")
    sh(w.user, "git", "push", "-q", "origin", "master")

    # --- next agent task begins with pull: decisions are applied and reported
    out = pull(w.cfg)
    d = out["decisions"]
    assert (d["accepted"], d["rejected"], d["pending"]) == (["C-0002"], ["C-0001"], [])
    assert [o["id"] for o in out["open"]] == ["C-0001"]
    assert out["open"][0]["thread"] == ["Rejected: keep my wording"]
    assert agent_branch(w.cfg) is None  # all decided; branch cleaned up

    out = push(w.cfg)
    assert "outperforms most baselines" in w.remote_file("sections/results.tex")  # accepted change published
    assert "long sentence" in w.remote_file("sections/intro.tex")  # rejected change never published
    assert "No pending agent changes" in w.remote_file("redline.tex")
    assert "C-0002" in w.remote_file("review/CHANGELOG.md")
    assert git(repo, "tag", "--list").count("paper-review/pre-apply-") == 1  # local rollback point
    assert "paper-review/pre-apply" not in sh(w.bare.parent, "git", "--git-dir", str(w.bare), "tag", "--list")


@needs_latexdiff
def test_researcher_edits_during_a_round_do_not_pollute_the_redline(world):
    w, repo = world, world.repo
    pull(w.cfg)
    sh(repo, "git", "switch", "-q", "-c", "agent/round-1")
    agent_commit(repo, "sections/results.tex", "always outperforms", "outperforms", "Soften\n\nResolves: C-0002")
    sh(repo, "git", "switch", "-q", "master")
    push(w.cfg)

    # while the agent branch is open the researcher edits an unrelated paragraph in Overleaf
    w.user_edit("sections/intro.tex", "Another intro paragraph", "A second intro paragraph", "researcher edit")
    user_sha = sh(w.user, "git", "rev-parse", "HEAD").strip()
    out = pull(w.cfg)
    assert out["warnings"] == [] and out["redline"].startswith("1 change(s)")
    meta = json.loads((w.cfg.review_path / "redline.json").read_text())
    assert [e["key"] for e in meta["entries"]] == ["C-0002"]  # only the agent's change
    redline = (w.cfg.redline_path).read_text()
    assert "A second intro paragraph" in redline and "\\DIFdel{A second" not in redline  # not shown as reverted
    sh(repo, "git", "merge-base", "--is-ancestor", user_sha, "agent/round-1")  # agent branch rebased onto it

    # repeated pulls / pushes are no-ops: no rebase or redline churn, no new commits
    head, branch_head = git(repo, "rev-parse", "HEAD"), git(repo, "rev-parse", "agent/round-1")
    for _ in range(2):
        out = pull(w.cfg)
        assert out["redline"] == "unchanged" and out["fetched_commits"] == 0
    push(w.cfg)
    assert git(repo, "rev-parse", "HEAD") == head and git(repo, "rev-parse", "agent/round-1") == branch_head


def test_init_local_writes_remote_config_and_no_workflow(repo, cli):
    cli("init", "--local")
    cfg_text = (repo / ".paper-review.yml").read_text()
    assert "remote: origin" in cfg_text and "remote_branch" not in cfg_text  # branch name is detected
    assert not (repo / ".github").exists()


@needs_latexdiff
def test_push_migrates_a_legacy_review_redline(world):
    """A repo that still has the pre-move review/redline.tex ends up with only the new file,
    even when the redline itself is already current."""
    w, repo = world, world.repo
    pull(w.cfg)
    sh(repo, "git", "switch", "-q", "-c", "agent/round-1")
    agent_commit(repo, "sections/results.tex", "always outperforms", "outperforms", "Soften\n\nResolves: C-0002")
    sh(repo, "git", "switch", "-q", "master")
    push(w.cfg)  # redline is now current at the new location
    (repo / "review" / "redline.tex").write_text("%% paper-review redline (generated)\n%% decision[C-0002]: pending\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "legacy redline from an older version")
    assert push(w.cfg)["redline"] != "unchanged"
    tree = sh(w.bare.parent, "git", "--git-dir", str(w.bare), "ls-tree", "-r", "--name-only", "master").split()
    assert "redline.tex" in tree and "review/redline.tex" not in tree


def test_address_cli_is_atomic_and_reads_json_from_a_file(world, tmp_path):
    from paper_review.cli import main as cli_main

    w = world
    pull(w.cfg)
    spec = tmp_path / "edit.json"
    spec.write_text(json.dumps({
        "edits": [{"file": "sections/results.tex", "old": "always outperforms the baselines",
                   "new": "outperforms most baselines"}],
        "reply": "Softened the claim.", "commit_message": "Soften claim"}))
    assert cli_main(["--root", str(w.repo), "address", "C-0002", str(spec)]) == 0
    msg = git(w.repo, "log", "-1", "--format=%B")
    assert msg.startswith("Soften claim") and "Resolves: C-0002" in msg
    assert Store(w.cfg).get("C-0002")["thread"][-1]["body"] == "Softened the claim."
    # a bad edit exits non-zero and changes nothing
    spec.write_text(json.dumps({"edits": [{"file": "sections/intro.tex", "old": "nope", "new": "x"}], "reply": "r"}))
    head = git(w.repo, "rev-parse", "HEAD")
    assert cli_main(["--root", str(w.repo), "address", "C-0001", str(spec)]) == 1
    assert git(w.repo, "rev-parse", "HEAD") == head and sh(w.repo, "git", "status", "--porcelain").strip() == ""


def test_init_writes_the_claude_code_wiring(repo, cli):
    cli("init", "--local")
    assert json.loads((repo / ".mcp.json").read_text())["mcpServers"]["paper-review"]["args"] == ["mcp"]
    assert "Address the open review comments" in (repo / ".claude" / "commands" / "address-comments.md").read_text()
    claude = " ".join((repo / "CLAUDE.md").read_text().split())  # ignore line wrapping
    assert "@AGENTS.md" in claude and "Never push a branch to Overleaf" in claude
    agents = (repo / "AGENTS.md").read_text()
    assert "address_comment" in agents and "paper-review address" in agents and "Never push a branch" in agents
