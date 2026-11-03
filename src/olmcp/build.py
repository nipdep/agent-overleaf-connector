"""Build the paper and the artifacts agents and humans need.

Outputs under ``<build_dir>/``: ``paper.pdf``, ``paper.synctex.gz``,
``pages/p-NNN.png``, ``text.json`` (per-page text and word boxes) and
``build.json`` (provenance and warnings).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, detect_engine, detect_main
from .gitutil import rev_parse

ENGINE_FLAG = {"pdflatex": "-pdf", "xelatex": "-xelatex", "lualatex": "-lualatex"}


class BuildError(RuntimeError):
    pass


def run_latexmk(cfg: Config, main: str, engine: str) -> tuple[Path, str]:
    if not shutil.which("latexmk"):
        raise BuildError("latexmk not found. Install TeX Live or use the docker image (docker/Dockerfile).")
    outdir = cfg.build_path
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "latexmk", ENGINE_FLAG[engine], "-synctex=1", "-interaction=nonstopmode",
        "-file-line-error", "-halt-on-error", f"-outdir={cfg.build_dir}", main,
    ]
    proc = subprocess.run(cmd, cwd=cfg.root, capture_output=True, text=True)
    log = proc.stdout + proc.stderr
    pdf = outdir / (Path(main).stem + ".pdf")
    if proc.returncode != 0 or not pdf.exists():
        tail = "\n".join(log.strip().splitlines()[-25:])
        raise BuildError(f"latexmk failed (exit {proc.returncode}). Last lines:\n{tail}")
    return pdf, log


def extract_pages(pdf: Path, outdir: Path, dpi: int) -> list[dict]:
    import pymupdf

    pages_dir = outdir / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True)
    pages = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            page.get_pixmap(dpi=dpi).save(pages_dir / f"p-{i:03d}.png")
            words = [[round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1), w[4]]
                     for w in page.get_text("words")]
            pages.append({
                "page": i,
                "width": round(page.rect.width, 1),
                "height": round(page.rect.height, 1),
                "text": page.get_text("text"),
                "words": words,
            })
    return pages


def warnings_from_log(log: str) -> dict:
    return {
        "latex_warnings": len(re.findall(r"LaTeX Warning:", log)),
        "overfull_boxes": len(re.findall(r"Overfull \\[hv]box", log)),
        "undefined_refs": len(re.findall(r"Warning: (?:Reference|Citation)", log)),
    }


def build(cfg: Config) -> dict:
    main = detect_main(cfg)
    engine, how = detect_engine(cfg)
    pdf, log = run_latexmk(cfg, main, engine)
    final_log = pdf.with_suffix(".log")  # last pass only; latexmk stdout repeats every pass
    if final_log.exists():
        log = final_log.read_text(encoding="utf-8", errors="replace")
    out = cfg.build_path
    final = out / "paper.pdf"
    shutil.copyfile(pdf, final)
    synctex = out / (Path(main).stem + ".synctex.gz")
    if synctex.exists():
        shutil.copyfile(synctex, out / "paper.synctex.gz")
    pages = extract_pages(final, out, cfg.page_dpi)
    (out / "text.json").write_text(json.dumps({"pages": pages}, ensure_ascii=False), encoding="utf-8")
    info = {
        "commit": rev_parse(cfg.root, "HEAD"),
        "main": main,
        "engine": engine,
        "engine_source": how,
        "pages": len(pages),
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **warnings_from_log(log),
    }
    (out / "build.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


def load_text(cfg: Config) -> list[dict]:
    p = cfg.build_path / "text.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("pages", [])
