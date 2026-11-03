"""The review loop as MCP tools: protocol rules are enforced in code, and the real server
speaks MCP over stdio."""

import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")

from olmcp.gitutil import git  # noqa: E402
from olmcp.review_tools import PaperTools, ToolError  # noqa: E402
from olmcp.store import Store  # noqa: E402

from conftest import needs_latexdiff, sh  # noqa: E402

SOFTEN = {"file": "sections/results.tex",
          "old": "always outperforms the baselines", "new": "outperforms most baselines"}


def head_message(repo):
    return git(repo, "log", "-1", "--format=%B")


def test_address_comment_is_one_atomic_commit_in_direct_mode(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    out = t.address_comment("C-0002", [SOFTEN], "Softened the claim to 'most baselines'.")
    assert out["status"] == "addressed" and out["branch"] == "master" and "outperforms most baselines" in out["diff"]
    assert "Resolves: C-0002" in head_message(w.repo)
    results = (w.repo / "sections" / "results.tex").read_text()
    assert "outperforms most baselines" in results and "@agent" not in results  # marker removed
    c = Store(w.cfg).get("C-0002")
    assert c["status"] == "addressed" and c["thread"][-1] == {**c["thread"][-1], "author": "agent"}
    assert "most baselines" in c["thread"][-1]["body"]
    assert sh(w.repo, "git", "status", "--porcelain").strip() == ""

    t.push()
    assert "outperforms most baselines" in w.remote_file("sections/results.tex")


@needs_latexdiff
def test_suggest_mode_uses_a_local_round_branch_and_never_touches_master(world):
    w, repo = world, world.repo
    (repo / ".olmcp.yml").write_text("mode: suggest\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "suggest mode")
    t = PaperTools(repo)
    t.pull()
    master_before = git(repo, "rev-parse", "master").strip()

    a = t.address_comment("C-0002", [SOFTEN], "Softened.")
    assert a["branch"] == "agent/round-1" and a["status"] == "addressed"
    b = t.address_comment("C-0001", [{"file": "sections/intro.tex", "old": "in a long sentence",
                                      "new": "briefly"}], "Shortened.")
    assert b["branch"] == "agent/round-1"  # the same round continues
    assert git(repo, "rev-parse", "master").strip() == master_before
    assert git(repo, "rev-list", "--count", "master..agent/round-1").strip() == "2"

    out = t.push()
    assert out["redline"].startswith("2 change(s)")
    assert "decision[C-0001]" in w.remote_file("redline.tex")
    assert "always outperforms" in w.remote_file("sections/results.tex")  # nothing applied yet
    assert "agent/round-1" not in sh(w.bare.parent, "git", "--git-dir", str(w.bare), "branch", "--list")


@pytest.mark.parametrize("bad_edit, why", [
    ({**SOFTEN, "old": "this text does not exist"}, "found 0"),
    ({**SOFTEN, "old": "e"}, "found"),  # appears more than once
    ({**SOFTEN, "old": ""}, "non-empty"),
    ({**SOFTEN, "new": SOFTEN["old"]}, "differs"),
])
def test_bad_edits_change_nothing(world, bad_edit, why):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    head = git(w.repo, "rev-parse", "HEAD")
    with pytest.raises(ToolError, match=why):
        t.address_comment("C-0002", [SOFTEN | {"file": "sections/intro.tex", "old": "Another intro", "new": "A second intro"},
                                     bad_edit], "reply")
    assert git(w.repo, "rev-parse", "HEAD") == head  # no commit
    assert sh(w.repo, "git", "status", "--porcelain").strip() == ""  # first edit was not left behind
    assert "A second intro" not in (w.repo / "sections" / "intro.tex").read_text()
    assert Store(w.cfg).get("C-0002")["status"] == "open" and not Store(w.cfg).get("C-0002")["thread"]


@needs_latexdiff
def test_failed_edit_in_suggest_mode_leaves_no_empty_branch(world):
    w, repo = world, world.repo
    (repo / ".olmcp.yml").write_text("mode: suggest\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "suggest mode")
    t = PaperTools(repo)
    t.pull()
    with pytest.raises(ToolError):
        t.address_comment("C-0002", [{**SOFTEN, "old": "nope"}], "reply")
    assert git(repo, "branch", "--list", "agent/*").strip() == ""
    assert git(repo, "branch", "--show-current").strip() == "master"


@pytest.mark.parametrize("path", [
    "../outside.tex", "/etc/passwd", ".git/config", "review/comments/C-0001.json",
    "build/x.tex", "figures/a.png", "sections/missing.tex",
])
def test_edits_are_confined_to_the_paper(world, path):
    t = PaperTools(world.repo)
    t.pull()
    with pytest.raises(ToolError):
        t.address_comment("C-0002", [{"file": path, "old": "x", "new": "y"}], "reply")


def test_reads_are_confined_too_and_symlinks_cannot_escape(world, tmp_path):
    w = world
    secret = tmp_path / "secret.tex"
    secret.write_text("secret outside the repo\n")
    (w.repo / "sections" / "link.tex").symlink_to(secret)
    t = PaperTools(w.repo)
    for bad in (".git/config", "../secret.tex", "sections/link.tex"):
        with pytest.raises(ToolError):
            t.read_file(bad)
    ok = t.read_file("sections/results.tex", 1, 2)
    assert ok["start_line"] == 1 and "\\section{Results}" in ok["text"]


def test_needs_a_reply_edits_and_a_clean_tree(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    with pytest.raises(ToolError, match="reply is required"):
        t.address_comment("C-0002", [SOFTEN], "  ")
    with pytest.raises(ToolError, match="at least one edit"):
        t.address_comment("C-0002", [], "reply")
    with pytest.raises(ToolError, match="no such comment"):
        t.address_comment("C-9999", [SOFTEN], "reply")
    (w.repo / "sections" / "intro.tex").write_text("dirty\n")
    with pytest.raises(ToolError, match="uncommitted"):
        t.address_comment("C-0002", [SOFTEN], "reply")


def test_reply_without_editing_keeps_the_comment_open_and_is_published(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    t.reply_to_comment("C-0001", "Do you mean the first sentence or the whole paragraph?")
    assert Store(w.cfg).get("C-0001")["status"] == "open"
    t.push()
    remote = json.loads(w.remote_file("review/comments/C-0001.json"))
    assert remote["thread"][-1]["author"] == "agent" and "first sentence" in remote["thread"][-1]["body"]


def test_list_and_show_comment(world):
    w = world
    t = PaperTools(w.repo)
    t.pull()
    items = t.list_comments()
    assert [i["id"] for i in items] == ["C-0001", "C-0002"] and items[1]["file"] == "sections/results.tex"
    shown = t.show_comment("C-0002")
    assert "always outperforms" in shown["source_context"] and shown["source_context_first_line"] >= 1
    t.address_comment("C-0002", [SOFTEN], "done")
    assert [i["id"] for i in t.list_comments()] == ["C-0001"]
    assert [i["id"] for i in t.list_comments(status="addressed")] == ["C-0002"]


def _text(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def test_the_server_speaks_mcp_over_stdio(world):
    """Spawn the real server and drive it as a client would (Claude Code, Codex...)."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    w = world
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "olmcp.cli", "--root", str(w.repo), "mcp"])

    async def session():
        async with Client(params) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            pulled = _text(await client.call_tool("pull", {}))
            listed = await client.call_tool("list_comments", {})
            done = await client.call_tool("address_comment", {
                "comment_id": "C-0002", "edits": [SOFTEN], "reply": "Softened the claim."})
            bad = await client.call_tool("address_comment", {
                "comment_id": "C-0001", "edits": [{**SOFTEN, "old": "nope"}], "reply": "x"})
            return names, pulled, listed, done, bad

    names, pulled, listed, done, bad = asyncio.run(session())
    assert {"pull", "list_comments", "show_comment", "read_file", "address_comment",
            "reply_to_comment", "push", "build", "view_page"} <= names
    assert pulled["comments"]["new"] == ["C-0001", "C-0002"]
    assert not listed.is_error
    assert not done.is_error and "Resolves: C-0002" in head_message(w.repo)
    assert bad.is_error and "exactly once" in json.dumps([c.model_dump() for c in bad.content])
