"""Optional hashtags in comments: #agent (focus), #no-agent (hands off), #suggest / #direct (mode)."""

import json

import pytest

pytest.importorskip("mcp")

from olmcp.cli import main  # noqa: E402
from olmcp.config import load_config  # noqa: E402
from olmcp.gitutil import git  # noqa: E402
from olmcp.local import pull  # noqa: E402
from olmcp.modes import Tags, parse_tags, skip_reasons, strip_tags  # noqa: E402
from olmcp.review_tools import PaperTools, ToolError  # noqa: E402
from olmcp.store import Store  # noqa: E402

from conftest import sh  # noqa: E402

SOFTEN = {"file": "sections/results.tex", "old": "always outperforms the baselines",
          "new": "outperforms most baselines"}
ABLATION = {"file": "sections/results.tex", "old": "The ablation study is unchanged.",
            "new": "The ablation study is unchanged in every setting."}
SHORTEN = {"file": "sections/intro.tex", "old": "in a long sentence", "new": "briefly"}


@pytest.mark.parametrize("text, agent, mode", [
    ("we need to fix the wording in here to shorten this #agent #suggest", True, "suggest"),
    ("#no-agent note for Alice", False, None),
    ("see #noagent", False, None),
    ("#NO-AGENT shout", False, None),
    ("fix this #direct", None, "direct"),
    ("tag at the end #direct.", None, "direct"),
    ("(#suggest) go ahead", None, "suggest"),
    ("#agent #no-agent", False, None),            # conflict: hands off wins
    ("#suggest #direct", None, "suggest"),        # conflict: hold for review wins
    ("[direct] but #suggest", None, "suggest"),   # a hashtag beats the legacy form
    ("[suggest] legacy start", None, "suggest"),
    ("direct: legacy start", None, "direct"),
    ("the #agentive turn in #agent-based design", None, None),   # longer words are not tags
    ("a#agent b", None, None),                    # glued to other text
    ("see https://x.org/page.html#direct and https://y.org/#suggest", None, None),   # URL fragments
    ("macro arguments #1 and #2", None, None),    # LaTeX parameters
    ("direct the reader to Figure 2", None, None),
    ("", None, None),
])
def test_how_tags_are_read(text, agent, mode):
    assert parse_tags(text) == Tags(agent, mode)


def test_tags_can_be_switched_off():
    assert parse_tags("fix #agent #suggest", enabled=False) == Tags()


def test_tags_are_removed_for_short_summaries():
    assert strip_tags("fix the wording #agent #suggest please") == "fix the wording please"
    assert strip_tags("[suggest] tighten this") == "tighten this"
    assert strip_tags("no tags here") == "no tags here"


def c(cid, status="open", agent=None):
    d = {"id": cid, "status": status}
    if agent is not None:
        d["agent"] = agent
    return d


def test_when_the_agent_should_leave_a_comment_alone():
    assert skip_reasons([c("C-1"), c("C-2")]) == {}                                   # untagged: nothing changes
    assert skip_reasons([c("C-1"), c("C-2", agent=False)]) == {"C-2": "no-agent"}
    focused = [c("C-1", agent=True), c("C-2"), c("C-3", "addressed"), c("C-4", agent=False)]
    assert skip_reasons(focused) == {"C-2": "focus", "C-4": "no-agent"}               # C-3 is not open: not skipped
    assert skip_reasons([c("C-1", "addressed", agent=True), c("C-2")]) == {}          # focus ends with the tagged one


def tagged_world(w, extra=""):
    """Three markers: C-0001 #no-agent, C-0002 #agent #suggest, C-0003 untagged."""
    intro = w.repo / "sections" / "intro.tex"
    intro.write_text(intro.read_text().replace("tighten this opening sentence", "tighten this opening sentence #no-agent"))
    res = w.repo / "sections" / "results.tex"
    text = res.read_text().replace("soften this claim and add a citation", "soften this claim #agent #suggest")
    text = text.replace("The ablation study is unchanged.", "%% @agent: ablation sentence\nThe ablation study is unchanged.")
    res.write_text(text)
    sh(w.repo, "git", "commit", "-qam", "tag the markers" + extra)


def test_a_marker_carries_the_tags(world):
    w = world
    tagged_world(w)
    PaperTools(w.repo).pull()
    store = Store(w.cfg)
    assert store.get("C-0001")["agent"] is False and "mode" not in store.get("C-0001")
    assert store.get("C-0002")["agent"] is True and store.get("C-0002")["mode"] == "suggest"
    assert "agent" not in store.get("C-0003") and "mode" not in store.get("C-0003")


def test_the_agent_sees_only_what_it_should_and_cannot_touch_hands_off_comments(world):
    w = world
    tagged_world(w)
    t = PaperTools(w.repo)
    t.pull()
    assert [x["id"] for x in t.list_comments()] == ["C-0002"]            # focus on #agent; #no-agent hidden
    everything = {x["id"]: x for x in t.list_comments(include_skipped=True)}
    assert {k: (v["for_agent"], v["skipped_because"]) for k, v in everything.items()} == {
        "C-0001": (False, "no-agent"), "C-0002": (True, None), "C-0003": (False, "focus")}
    shown = t.show_comment("C-0001")
    assert shown["for_agent"] is False and shown["skipped_because"] == "no-agent" and shown["agent_tag"] is False

    head = git(w.repo, "rev-parse", "HEAD")
    with pytest.raises(ToolError, match="#no-agent"):
        t.address_comment("C-0001", [SHORTEN], "r")
    with pytest.raises(ToolError, match="#no-agent"):
        t.reply_to_comment("C-0001", "hello")
    assert git(w.repo, "rev-parse", "HEAD") == head and sh(w.repo, "git", "status", "--porcelain").strip() == ""
    assert not Store(w.cfg).get("C-0001")["thread"]

    # focus is a default, not a wall: the researcher can still ask for everything
    out = t.address_comment("C-0003", [ABLATION], "Extended.")
    assert out["status"] == "addressed" and out["mode"] == "direct"
    # the tagged comment uses its own mode
    assert t.address_comment("C-0002", [SOFTEN], "Softened.")["mode"] == "suggest"
    # focus clears itself: nothing tagged is open any more, #no-agent stays hidden
    assert t.list_comments() == []
    assert [x["id"] for x in t.list_comments(include_skipped=True)] == ["C-0001"]


def test_focus_ends_by_itself_so_untagged_comments_come_back(world):
    w = world
    tagged_world(w)
    t = PaperTools(w.repo)
    t.pull()
    assert [x["id"] for x in t.list_comments()] == ["C-0002"]
    t.address_comment("C-0002", [SOFTEN], "Softened.")
    assert [x["id"] for x in t.list_comments()] == ["C-0003"]            # C-0001 stays #no-agent


def test_pull_says_what_is_in_focus_and_what_is_hands_off(world, capsys):
    w = world
    tagged_world(w)
    out = pull(w.cfg)
    assert out["focus"] == ["C-0002"]
    assert {(s["id"], s["why"]) for s in out["skipped"]} == {("C-0001", "no-agent"), ("C-0003", "focus")}
    assert [o["id"] for o in out["open"]] == ["C-0002"]
    assert main(["--root", str(w.repo), "pull"]) == 0
    text = capsys.readouterr().out
    assert "focus: only the #agent comments (C-0002)" in text and "skipped: C-0003" in text
    assert "hands off (#no-agent): C-0001" in text
    assert "C-0002 [#agent] [suggest]" in text
    assert main(["--root", str(w.repo), "list"]) == 0
    listing = capsys.readouterr().out
    assert "C-0001 [#no-agent]" in listing and "C-0002 [#agent] [suggest]" in listing


def test_untagged_comments_behave_exactly_as_before(world):
    w = world
    t = PaperTools(w.repo)
    out = pull(w.cfg)
    assert out["focus"] == [] and out["skipped"] == [] and [o["id"] for o in out["open"]] == ["C-0001", "C-0002"]
    assert [x["id"] for x in t.list_comments()] == ["C-0001", "C-0002"]
    assert all(x["for_agent"] and x["skipped_because"] is None for x in t.list_comments())


def test_tags_can_be_turned_off_so_hashtags_are_just_text(world):
    w = world
    (w.repo / ".olmcp.yml").write_text("comment_tags: false\n")
    tagged_world(w)
    t = PaperTools(w.repo)
    t.pull()
    store = Store(load_config(w.repo))
    assert all("agent" not in store.get(i) and "mode" not in store.get(i) for i in ("C-0001", "C-0002", "C-0003"))
    assert [x["id"] for x in t.list_comments()] == ["C-0001", "C-0002", "C-0003"]


def test_the_redline_shows_what_was_asked_without_the_tags(world):
    from olmcp.redline import _request

    w = world
    PaperTools(w.repo).pull()
    store = Store(w.cfg)
    cm = store.get("C-0002")
    cm["body"] = "soften this claim #agent #suggest and add a citation"
    store.save(cm)
    assert _request(w.cfg, {"comment_ids": ["C-0002"], "subject": "x"}) == "soften this claim and add a citation"
