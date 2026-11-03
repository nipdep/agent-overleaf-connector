import json

from olmcp import anchor
from olmcp.config import detect_engine, detect_main, load_config
from olmcp.markers import parse_markers, strip_marker_lines
from olmcp.store import Store
from olmcp.sync import sync

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
    assert Store(load_config(repo)).get("C-0002")["status"] == "addressed"  # the agent never closes a comment
    cli("round")
    assert capsys.readouterr().out.strip().endswith("agent/round-1")


def test_init_never_overwrites_existing_agents_md(repo, cli):
    (repo / "AGENTS.md").write_text("mine\n")
    cli("init")
    assert (repo / "AGENTS.md").read_text() == "mine\n"
    assert (repo / "review" / "AGENTS.md").exists()
    assert (repo / ".olmcp.yml").exists()
    assert "build/" in (repo / ".gitignore").read_text()
    wf = (repo / ".github" / "workflows" / "olmcp.yml").read_text()
    assert 'branches: ["main", "agent/**"]' in wf
    sh(repo, "git", "status", "--short")


def test_generated_redline_is_neither_the_main_file_nor_scanned_for_markers(repo):
    # a main file whose name sorts AFTER "redline.tex", so a naive detector would pick the redline
    (repo / "main.tex").rename(repo / "zeta.tex")
    (repo / "redline.tex").write_text(
        "%% olmcp redline (generated). Edit ONLY the decision lines.\n"
        "%% @agent: this must not become a comment\n"
        "\\documentclass{article}\n\\begin{document}x\\end{document}\n")
    cfg = load_config(repo)
    assert detect_main(cfg) == "zeta.tex"
    assert all(c["body"] != "this must not become a comment" for c in
               (Store(cfg).all() + [{"body": m.text} for m in __import__("olmcp.markers", fromlist=["scan"]).scan(cfg)]))
    # but a user's own file that happens to be called redline.tex is still scanned
    (repo / "redline.tex").write_text("%% @agent: mine\nMy text.\n")
    from olmcp.markers import scan
    assert [m.text for m in scan(load_config(repo))].count("mine") == 1


def test_redline_sits_beside_the_main_file(repo):
    cfg = load_config(repo)
    assert cfg.redline_path == repo / "redline.tex" and cfg.redline_rel == "redline.tex"
    cfg2 = load_config(repo)
    cfg2.main = "paper/main.tex"
    assert cfg2.redline_rel == "paper/redline.tex"  # same folder as the real main (paper-root handling comes with --main)


def test_the_old_config_name_still_works_and_init_migrates_it(repo, cli):
    (repo / ".paper-review.yml").write_text("mode: suggest\nengine: lualatex\n")
    cfg = load_config(repo)
    assert cfg.mode == "suggest" and cfg.engine == "lualatex"  # read from the old name
    cli("init", "--local")
    assert not (repo / ".paper-review.yml").exists()
    new = (repo / ".olmcp.yml").read_text()
    assert "mode: suggest" in new and "engine: lualatex" in new  # settings kept
    assert load_config(repo).mode == "suggest"


def test_the_old_alias_and_module_name_are_declared(tmp_path):
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    from pathlib import Path

    meta = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert meta["project"]["name"] == "agent-overleaf-connector"
    assert meta["project"]["scripts"] == {"olmcp": "olmcp.cli:main", "paper-review": "olmcp.cli:main"}


def test_crop_to_change_keeps_the_changed_words_and_a_little_context():
    from olmcp.textdiff import crop_to_change, word_diff

    long = " ".join(f"w{i}" for i in range(60))
    d = word_diff(long + " old " + long, long + " new " + long)
    c = crop_to_change(d, context=20)
    assert "[-old-]{+new+}" in c and c.startswith("...") and c.endswith("...") and len(c) < 120
    assert crop_to_change("no change here at all") == "no change here at all"
    assert crop_to_change(word_diff("a b", "a c")) == "a [-b-]{+c+}"


def test_word_diff_ignores_whitespace_and_keeps_punctuation_attached():
    from olmcp.textdiff import word_diff

    assert word_diff("agents in a long sentence.", "agents in one sentence.") == "agents in [-a long-]{+one+} sentence."
    assert word_diff("is unchanged.", "is unchanged in every setting.") == "is unchanged {+in every setting+}."
    assert word_diff("  leading  space", "leading space") == "leading space"  # no stray empty insert
    assert word_diff("use \\emph{old} text", "use \\emph{new} text") == "use \\emph{[-old-]{+new+}} text"
