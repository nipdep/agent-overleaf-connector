import json

from paper_review import anchor
from paper_review.config import detect_engine, detect_main, load_config
from paper_review.markers import parse_markers, strip_marker_lines
from paper_review.store import Store
from paper_review.sync import sync

from conftest import sh


def test_parse_markers_with_continuation_and_quote():
    text = "\\section{A}\n%% @agent: soften this\n%% | and cite\nOur claim is bold.\nSecond line.\n\nOther.\n"
    (m,) = parse_markers(text, "a.tex")
    assert m.text == "soften this and cite"
    assert (m.line, m.end_line) == (2, 3)
    assert m.quote == "Our claim is bold.\nSecond line."


def test_marker_id_stable_when_line_moves():
    a = parse_markers("%% @agent: x\npara\n", "f.tex")[0]
    b = parse_markers("\n\n\n%% @agent: x\npara\n", "f.tex")[0]
    assert a.external_id == b.external_id
    assert a.external_id != parse_markers("%% @agent: y\npara\n", "f.tex")[0].external_id


def test_strip_marker_lines():
    text = "a\n%% @agent: x\n%% | more\nb\n"
    assert strip_marker_lines(text) == "a\nb\n"


def test_latex_to_plain_and_find_page():
    plain = anchor.latex_to_plain(r"Our \textbf{method} always outperforms~\cite{x} the baselines. % hidden")
    assert plain == "Our method always outperforms the baselines."
    pages = [{"page": 1, "text": "Intro\nsomething else"},
             {"page": 2, "text": "Results\nOur method always outperforms the baselines on all benchmarks."}]
    assert anchor.find_page(plain, pages)[0] == 2
    assert anchor.find_page("completely unrelated text here", pages) is None


def test_detect_main_and_engine(repo):
    cfg = load_config(repo)
    assert detect_main(cfg) == "main.tex"
    assert detect_engine(cfg)[0] == "pdflatex"
    (repo / "main.tex").write_text("% !TEX program = xelatex\n" + (repo / "main.tex").read_text())
    assert detect_engine(load_config(repo)) == ("xelatex", "magic comment")


def test_sync_lifecycle(repo, cfg):
    r = sync(cfg)
    assert r.created == ["C-0001", "C-0002"]
    store = Store(cfg)
    c = store.get("C-0001")
    assert c["status"] == "open" and c["anchor"]["source"]["file"] == "sections/intro.tex"
    assert sync(cfg).changed is False  # idempotent

    # agent removes the marker -> addressed
    p = repo / "sections" / "intro.tex"
    p.write_text(p.read_text().replace("%% @agent: tighten this opening sentence\n", ""))
    assert sync(cfg).addressed == ["C-0001"]
    assert store.get("C-0001")["status"] == "addressed"

    # marker comes back -> reopened, same comment id
    p.write_text(p.read_text().replace("\\section{Intro}\n", "\\section{Intro}\n%% @agent: tighten this opening sentence\n"))
    assert sync(cfg).reopened == ["C-0001"]
    assert store.get("C-0001")["status"] == "open"
    assert len(store.all()) == 2


def test_cli_list_show_resolve(repo, cli, capsys):
    cli("sync")
    capsys.readouterr()
    cli("list", "--json")
    items = json.loads(capsys.readouterr().out)
    assert [i["id"] for i in items] == ["C-0001", "C-0002"]
    cli("show", "C-0002")
    out = capsys.readouterr().out
    assert "soften this claim" in out and "results.tex" in out and "Our method always" in out
    cli("resolve", "C-0002", "--note", "done")
    assert Store(load_config(repo)).get("C-0002")["status"] == "resolved"  # direct mode
    cli("round")
    assert capsys.readouterr().out.strip().endswith("agent/round-1")


def test_init_never_overwrites_existing_agents_md(repo, cli):
    (repo / "AGENTS.md").write_text("mine\n")
    cli("init")
    assert (repo / "AGENTS.md").read_text() == "mine\n"
    assert (repo / "review" / "AGENTS.md").exists()
    assert (repo / ".paper-review.yml").exists()
    assert "build/" in (repo / ".gitignore").read_text()
    wf = (repo / ".github" / "workflows" / "paper-review.yml").read_text()
    assert 'branches: ["main", "agent/**"]' in wf
    sh(repo, "git", "status", "--short")
