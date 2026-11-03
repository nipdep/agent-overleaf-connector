"""Native Overleaf comments via olcli (faked): import with the selected text, follow-ups, resolve,
replies posted back, failures never fatal."""

import json
import shlex
import sys
from pathlib import Path

import pytest

from paper_review import overleaf
from paper_review.config import load_config
from paper_review.gitutil import git
from paper_review.local import agent_branch, pull, push
from paper_review.review_tools import PaperTools
from paper_review.store import Store

from conftest import needs_latexdiff, sh

FAKE = Path(__file__).parent / "fake_olcli.py"
PROJECT = "6ae8eca020f2e6cc79d3e5a2"
SOFTEN = {"file": "sections/results.tex", "old": "always outperforms the baselines",
          "new": "outperforms most baselines"}


def thread(tid, text, quote, path="/sections/results.tex", line=3, resolved=False, mid="m1"):
    return {"threadId": tid, "docId": "doc1", "path": path, "position": 10, "line": line, "column": 0,
            "selectedText": quote, "resolved": resolved,
            "messages": [{"id": mid, "content": text, "timestamp": "2026-11-03T09:00:00Z",
                          "user": {"email": "researcher@example.com"}}]}


@pytest.fixture
def ov(world, tmp_path, monkeypatch):
    """world + Overleaf comments enabled, backed by the fake olcli."""
    state = tmp_path / "olcli_state.json"
    state.write_text(json.dumps({"threads": []}))
    monkeypatch.setenv("FAKE_OLCLI_STATE", str(state))
    w = world
    (w.repo / ".paper-review.yml").write_text(
        f"overleaf_project: {PROJECT}\nolcli: {json.dumps(shlex.join([sys.executable, str(FAKE)]))}\n")
    sh(w.repo, "git", "add", "-A")
    sh(w.repo, "git", "commit", "-qm", "enable Overleaf comments")

    def read():
        return json.loads(state.read_text())["threads"]

    def write(threads):
        state.write_text(json.dumps({"threads": threads}))

    w.cfg = load_config(w.repo)
    w.state_read, w.state_write = read, write
    return w


def test_native_comment_arrives_with_its_selected_text(ov):
    w = ov
    w.state_write([thread("T1", "make this less absolute", "always outperforms the baselines")])
    out = pull(w.cfg)
    assert out["overleaf"]["created"] == ["C-0003"]  # C-0001/2 are the %% markers
    c = Store(w.cfg).get("C-0003")
    assert c["body"] == "make this less absolute" and c["author"] == "human:researcher@example.com"
    assert c["origin"]["type"] == "overleaf" and c["origin"]["thread_id"] == "T1"
    assert c["anchor"]["quote"] == "always outperforms the baselines"
    assert c["anchor"]["source"] == {"file": "sections/results.tex", "line": 3, "confidence": 1.0}
    entry = next(o for o in out["open"] if o["id"] == "C-0003")
    assert entry["selected_text"] == "always outperforms the baselines" and entry["from"] == "overleaf"
    # the agent-facing tools expose the selected range
    shown = PaperTools(w.repo).show_comment("C-0003")
    assert shown["selected_text"] == "always outperforms the baselines" and shown["from"] == "overleaf"
    assert "C-0003" in [i["id"] for i in PaperTools(w.repo).list_comments()]
    # importing again changes nothing
    again = pull(w.cfg)
    assert again["overleaf"]["created"] == [] and sh(w.repo, "git", "status", "--porcelain").strip() == ""


def test_stale_line_numbers_are_corrected_by_searching_the_quote(ov):
    w = ov
    w.state_write([thread("T1", "x", "always outperforms the baselines", line=40)])
    pull(w.cfg)
    assert Store(w.cfg).get("C-0003")["anchor"]["source"] == {"file": "sections/results.tex", "line": 3, "confidence": 0.9}


def test_followups_resolution_and_deletion_are_mirrored(ov):
    w = ov
    w.state_write([thread("T1", "make this less absolute", "always outperforms the baselines"),
                   thread("T2", "cite something", "The ablation study is unchanged.", line=5)])
    pull(w.cfg)
    store = Store(w.cfg)
    assert store.get("C-0003")["status"] == "open" and store.get("C-0004")["status"] == "open"

    # the researcher writes again in T1; an [agent] message in T1 is not feedback
    ts = w.state_read()
    ts[0]["messages"] += [
        {"id": "m2", "content": "[agent] I softened it.", "user": {"email": "researcher@example.com"}},
        {"id": "m3", "content": "not enough, say 'some baselines'", "user": {"email": "researcher@example.com"}}]
    w.state_write(ts)
    out = pull(w.cfg)
    assert out["overleaf"]["followups"] == ["C-0003"]
    thread_bodies = [t["body"] for t in store.get("C-0003")["thread"]]
    assert thread_bodies == ["not enough, say 'some baselines'"]

    # resolved in Overleaf by the researcher / deleted there
    ts = w.state_read()
    ts[0]["resolved"] = True
    w.state_write(ts[:1])  # T2 deleted
    out = pull(w.cfg)
    assert out["overleaf"]["resolved_in_overleaf"] == ["C-0003"] and out["overleaf"]["deleted_in_overleaf"] == ["C-0004"]
    assert store.get("C-0003")["status"] == "resolved" and store.get("C-0004")["status"] == "wontfix"


def test_a_follow_up_reopens_a_comment_the_agent_had_handled(ov):
    w = ov
    w.state_write([thread("T1", "make this less absolute", "always outperforms the baselines")])
    pull(w.cfg)
    t = PaperTools(w.repo)
    t.address_comment("C-0003", [SOFTEN], "Softened.")
    assert Store(w.cfg).get("C-0003")["status"] == "resolved"
    ts = w.state_read()
    ts[0]["messages"].append({"id": "m9", "content": "still too strong", "user": {"email": "researcher@example.com"}})
    w.state_write(ts)
    assert pull(w.cfg)["overleaf"]["reopened_in_overleaf"] == ["C-0003"]
    assert Store(w.cfg).get("C-0003")["status"] == "open"


def test_agent_reply_lands_in_the_overleaf_thread_once_and_thread_is_resolved_in_direct_mode(ov):
    w = ov
    w.state_write([thread("T1", "make this less absolute", "always outperforms the baselines")])
    pull(w.cfg)
    PaperTools(w.repo).address_comment("C-0003", [SOFTEN], "Softened to 'most baselines'.")
    out = push(w.cfg)
    assert out["overleaf"] == {"replies_posted": ["C-0003"], "threads_resolved": ["C-0003"]}
    t1 = w.state_read()[0]
    assert t1["resolved"] is True
    assert [m["content"] for m in t1["messages"]][-1] == "[agent] Softened to 'most baselines'."
    n = len(t1["messages"])
    out = push(w.cfg)  # idempotent: nothing posted again
    assert out["overleaf"] == {"replies_posted": [], "threads_resolved": []}
    assert len(w.state_read()[0]["messages"]) == n
    assert Store(w.cfg).get("C-0003")["origin"]["resolve_pushed"] is True
    assert sh(w.repo, "git", "status", "--porcelain").strip() == ""
    assert "outperforms most baselines" in w.remote_file("sections/results.tex")


@needs_latexdiff
def test_suggest_mode_replies_now_and_resolves_the_thread_only_after_you_accept(ov):
    w, repo = ov, ov.repo
    (repo / ".paper-review.yml").write_text(repo.joinpath(".paper-review.yml").read_text() + "mode: suggest\n")
    sh(repo, "git", "commit", "-qam", "suggest mode")
    w.cfg = load_config(repo)
    w.state_write([thread("T1", "make this less absolute", "always outperforms the baselines")])
    pull(w.cfg)
    PaperTools(repo).address_comment("C-0003", [SOFTEN], "Softened to 'most baselines'.")
    assert agent_branch(w.cfg) == "agent/round-1"

    out = push(w.cfg)
    assert out["overleaf"]["replies_posted"] == ["C-0003"] and out["overleaf"]["threads_resolved"] == []
    t1 = w.state_read()[0]
    assert t1["resolved"] is False and t1["messages"][-1]["content"].startswith("[agent] Softened")
    assert "decision[C-0003]" in w.remote_file("redline.tex")

    # the researcher accepts in redline.tex
    sh(w.user, "git", "pull", "-q", "--rebase", "origin", "master")
    tex = w.user / "redline.tex"
    tex.write_text(tex.read_text().replace("decision[C-0003]: pending", "decision[C-0003]: accept"))
    sh(w.user, "git", "commit", "-qam", "accept")
    sh(w.user, "git", "push", "-q", "origin", "master")

    out = pull(w.cfg)
    assert out["decisions"]["accepted"] == ["C-0003"]
    assert out["overleaf_sync_back"]["threads_resolved"] == ["C-0003"]
    assert w.state_read()[0]["resolved"] is True  # closed in Overleaf's own panel
    assert Store(w.cfg).get("C-0003")["status"] == "resolved"


def test_a_broken_or_missing_olcli_is_a_warning_not_a_crash(ov, monkeypatch):
    w = ov
    w.state_write([thread("T1", "x", "always outperforms the baselines")])
    monkeypatch.setenv("FAKE_OLCLI_FAIL", "1")
    out = pull(w.cfg)
    assert any("session" in x or "expired" in x for x in out["warnings"]), out["warnings"]
    assert [c["id"] for c in Store(w.cfg).all()] == ["C-0001", "C-0002"]  # the %% markers still work
    assert push(w.cfg)["warnings"]
    (w.repo / ".paper-review.yml").write_text(f"overleaf_project: {PROJECT}\nolcli: definitely-not-installed-xyz\n")
    sh(w.repo, "git", "commit", "-qam", "bad olcli")
    out = pull(load_config(w.repo))
    assert any("olcli not found" in x for x in out["warnings"])


def test_parse_threads_accepts_the_documented_shapes():
    one = thread("T1", "hello", "quoted text")
    assert overleaf.parse_threads(json.dumps([one]))[0]["quote"] == "quoted text"
    wrapped = overleaf.parse_threads("some noise\n" + json.dumps({"comments": [one], "changes": []}))
    assert wrapped[0]["path"] == "sections/results.tex" and wrapped[0]["messages"][0]["author"] == "researcher@example.com"
    alias = {"thread_id": "T9", "file": "./a.tex", "selected_text": "q", "messages": [
        {"_id": "x", "text": "t", "user": {"first_name": "Ada", "last_name": "L"}}]}
    n = overleaf.parse_threads(json.dumps([alias, {"no": "id"}]))
    assert len(n) == 1 and n[0]["thread_id"] == "T9" and n[0]["path"] == "a.tex"
    assert n[0]["messages"][0] == {"id": "x", "text": "t", "author": "Ada L", "at": None}
    with pytest.raises(overleaf.OverleafError):
        overleaf.parse_threads("no json here")


def test_overleaf_check_command(ov, capsys):
    from paper_review.cli import main

    ov.state_write([thread("T1", "x", "always outperforms the baselines"),
                    thread("T2", "y", "", resolved=True)])
    assert main(["--root", str(ov.repo), "overleaf-check"]) == 0
    assert "2 thread(s), 1 open, 1 with selected text" in capsys.readouterr().out
    (ov.repo / ".paper-review.yml").write_text("mode: direct\n")
    assert main(["--root", str(ov.repo), "overleaf-check"]) == 1
