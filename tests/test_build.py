import json

from olmcp.build import build

from conftest import needs_latexmk


@needs_latexmk
def test_build_outputs_and_page_anchor(repo, cfg):
    info = build(cfg)
    assert info["pages"] == 1 and info["engine"] == "pdflatex"
    out = cfg.build_path
    for name in ("paper.pdf", "paper.synctex.gz", "text.json", "build.json", "pages/p-001.png"):
        assert (out / name).exists(), name
    text = json.loads((out / "text.json").read_text())["pages"][0]["text"]
    assert "Results" in text and text and (out / "pages" / "p-001.png").stat().st_size > 1000

    # comments pick up their page number from the built text
    from olmcp.store import Store
    from olmcp.sync import sync

    sync(cfg)
    assert Store(cfg).get("C-0002")["anchor"]["page"] == 1


@needs_latexmk
def test_build_failure_reports_log_tail(repo, cfg):
    import pytest

    from olmcp.build import BuildError

    (repo / "sections" / "results.tex").write_text("\\undefinedcommand\n")
    with pytest.raises(BuildError, match="Undefined control sequence"):
        build(cfg)
