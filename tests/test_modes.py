"""Direct vs suggest: a default you can switch, and a per-comment choice."""

import pytest

pytest.importorskip("mcp")

from olmcp.gitutil import git  # noqa: E402
from olmcp.modes import parse_mode_tag  # noqa: E402
from olmcp.review_tools import PaperTools, ToolError  # noqa: E402
from olmcp.store import Store  # noqa: E402
from olmcp.config import load_config  # noqa: E402

from conftest import needs_latexdiff, sh  # noqa: E402

SOFTEN = {"file": "sections/results.tex", "old": "always outperforms the baselines",
          "new": "outperforms most baselines"}
SHORTEN = {"file": "sections/intro.tex", "old": "in a long sentence", "new": "briefly"}
ABLATION = {"file": "sections/results.tex", "old": "The ablation study is unchanged.",
            "new": "The ablation study is unchanged in every setting."}


@pytest.mark.parametrize("text, expected", [
    ("[suggest] make this shorter", "suggest"), ("[Direct] fix the typo", "direct"),
    ("suggest: tighten this", "suggest"), ("  direct : fix it", "direct"), ("DIRECT: loud", "direct"),
    ("direct the reader to Figure 2", None),      # an ordinary sentence is not a tag
    ("we could suggest: a rewrite", None),        # only at the start
    ("(suggest) x", None), ("", None), ("make this [suggest]", None),
])
def test_how_a_comment_chooses_its_mode(text, expected):
    assert parse_mode_tag(text) == expected


def tag(w, cid, mode):
    store = Store(w.cfg)
    c = store.get(cid)
    c["mode"] = mode
    store.save(c)
    sh(w.repo, "git", "add", "-A")
    sh(w.repo, "git", "commit", "-qm", f"tag {cid} {mode}")


def test_a_marker_can_carry_the_choice(world):
    w = world
    p = w.repo / "sections" / "intro.tex"
    p.write_text(p.read_text().replace("%% @agent: tighten", "%% @agent: [suggest] tighten"))
    sh(w.repo, "git", "commit", "-qam", "tag the marker")
    PaperTools(w.repo).pull()
    store = Store(w.cfg)
    assert store.get("C-0001")["mode"] == "suggest" and "mode" not in store.get("C-0002")
    shown = PaperTools(w.repo).list_comments()
    assert [(c["id"], c["mode"], c["mode_chosen_by_researcher"]) for c in shown] == [
        ("C-0001", "suggest", True), ("C-0002", "direct", False)]


def test_the_researchers_tag_beats_the_agents_choice(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    tag(w, "C-0001", "suggest")
    head = git(w.repo, "rev-parse", "HEAD")
    with pytest.raises(ToolError, match="asked for 'suggest'"):
        t.address_comment("C-0001", [SHORTEN], "r", mode="direct")
    with pytest.raises(ToolError, match="mode must be one of"):
        t.address_comment("C-0002", [SOFTEN], "r", mode="whatever")
    assert git(w.repo, "rev-parse", "HEAD") == head and sh(w.repo, "git", "status", "--porcelain").strip() == ""
    # an untagged comment lets the agent choose
    out = t.address_comment("C-0002", [SOFTEN], "Softened.", mode="suggest")
    assert out["mode"] == "suggest" and out["branch"] == "agent/round-1"


@needs_latexdiff
def test_direct_and_suggest_edits_mix_in_one_round(world):
    w = world
    p = w.repo / "sections" / "results.tex"
    p.write_text(p.read_text().replace("The ablation study is unchanged.",
                                       "%% @agent: ablation sentence\nThe ablation study is unchanged."))
    sh(w.repo, "git", "commit", "-qam", "a third marker")
    t = PaperTools(w.repo)
    t.pull()  # C-0001 intro, C-0002 results #1, C-0003 results #2
    tag(w, "C-0001", "suggest")
    tag(w, "C-0003", "suggest")

    a = t.address_comment("C-0001", [SHORTEN], "Shortened.")          # suggest (tagged): on the round branch
    b = t.address_comment("C-0002", [SOFTEN], "Softened.")            # direct (default): on master at once
    c = t.address_comment("C-0003", [ABLATION], "Extended.")          # suggest (tagged), after a direct edit
    assert (a["mode"], a["branch"]) == ("suggest", "agent/round-1")
    assert (b["mode"], b["branch"]) == ("direct", "master")
    assert (c["mode"], c["branch"]) == ("suggest", "agent/round-1")

    # the round branch was brought up to date first: it contains the direct edit AND its own suggestions
    on_branch = sh(w.repo, "git", "show", "agent/round-1:sections/results.tex")
    assert "outperforms most baselines" in on_branch and "in every setting" in on_branch
    assert sh(w.repo, "git", "merge-base", "--is-ancestor", "master", "agent/round-1") == ""
    master_results = sh(w.repo, "git", "show", "master:sections/results.tex")
    assert "outperforms most baselines" in master_results and "in every setting" not in master_results
    assert "briefly" not in sh(w.repo, "git", "show", "master:sections/intro.tex")

    out = t.push()
    assert out["redline"].startswith("2 change(s)")
    redline = w.remote_file("redline.tex")
    assert "decision[C-0001]" in redline and "decision[C-0003]" in redline and "decision[C-0002]" not in redline
    assert "outperforms most baselines" in w.remote_file("sections/results.tex")   # the direct one is live
    assert "in every setting" not in w.remote_file("sections/results.tex")         # the suggestion is held


def test_changing_the_default_mode_is_one_command(repo, cli, capsys):
    assert cli("mode") in (0, None)
    assert "default mode: direct" in capsys.readouterr().out
    (repo / ".olmcp.yml").write_text("# my notes\nengine: xelatex\nmode: direct\nmain: main.tex\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "config")
    cli("mode", "suggest")
    text = (repo / ".olmcp.yml").read_text()
    assert "mode: suggest" in text and "# my notes" in text and "engine: xelatex" in text and "main: main.tex" in text
    assert git(repo, "log", "-1", "--format=%s").strip() == "olmcp: default mode suggest"
    assert load_config(repo).mode == "suggest"
    capsys.readouterr()
    cli("mode")
    assert "default mode: suggest" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli("mode", "sideways")


def test_the_default_mode_can_be_set_before_any_config_exists_and_via_the_tool(repo):
    t = PaperTools(repo)
    assert not (repo / ".olmcp.yml").exists()
    out = t.set_mode("suggest")
    assert out["default_mode"] == "suggest" and (repo / ".olmcp.yml").read_text() == "mode: suggest\n"
    assert load_config(repo).mode == "suggest"
    with pytest.raises(ToolError):
        t.set_mode("sideways")


def test_a_comment_that_is_addressed_follows_the_default_when_untagged(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    t.set_mode("suggest")
    out = t.address_comment("C-0002", [SOFTEN], "Softened.")
    assert out["mode"] == "suggest" and out["branch"] == "agent/round-1"
