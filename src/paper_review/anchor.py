"""Locate quoted text. Anchors are text quotes, never character offsets, so they
survive edits and rebuilds."""

from __future__ import annotations

import re

from rapidfuzz import fuzz


def normalize(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


def latex_to_plain(s: str) -> str:
    """Crude LaTeX to text, good enough for fuzzy matching against PDF text."""
    s = re.sub(r"(?<!\\)%.*", "", s)
    s = re.sub(r"\\(?:cite|ref|eqref|autoref|cref|label)\w*\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s)
    s = re.sub(r"[{}$~\\^_&]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def score(quote: str, text: str) -> float:
    q, t = normalize(quote), normalize(text)
    if not q or not t:
        return 0.0
    if q in t:
        return 100.0
    return float(fuzz.partial_ratio(q, t))


def find_page(quote: str, pages: list[dict], threshold: float = 80.0) -> tuple[int, float] | None:
    """Best matching page (1-based) for ``quote`` in build/text.json pages."""
    probe = quote[:160]
    best: tuple[int, float] | None = None
    for page in pages:
        sc = score(probe, page.get("text", ""))
        if best is None or sc > best[1]:
            best = (page["page"], sc)
    if best and best[1] >= threshold:
        return best
    return None
