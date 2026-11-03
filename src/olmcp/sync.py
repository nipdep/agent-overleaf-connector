"""Reconcile ``%% @agent:`` markers in the source with the comment store.

* new marker                      -> new open comment
* marker gone, comment still open -> comment becomes ``addressed``
* marker (re)appears              -> comment reopens
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import anchor
from .build import load_text
from .config import Config
from .gitutil import rev_parse
from .markers import scan
from .modes import parse_tags
from .store import Store


@dataclass
class SyncResult:
    created: list[str] = field(default_factory=list)
    reopened: list[str] = field(default_factory=list)
    addressed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.created or self.reopened or self.addressed or self.updated)


def sync(cfg: Config, author: str = "human") -> SyncResult:
    store = Store(cfg)
    result = SyncResult()
    pages = load_text(cfg)
    commit = rev_parse(cfg.root, "HEAD")
    present: set[str] = set()

    for m in scan(cfg):
        present.add(m.external_id)
        plain = anchor.latex_to_plain(m.quote)
        page = anchor.find_page(plain, pages) if pages and plain else None
        new_anchor = {
            "build_commit": commit,
            "page": page[0] if page else None,
            "quote": plain,
            "source": {"file": m.file, "line": m.line, "confidence": 1.0},
        }
        existing = store.by_external(m.external_id)
        if existing is None:
            c = store.new(
                body=m.text, author=author, anchor=new_anchor,
                mode=parse_tags(m.text, cfg.comment_tags).mode, agent=parse_tags(m.text, cfg.comment_tags).agent,
                origin={"type": "marker", "external_id": m.external_id},
            )
            result.created.append(c["id"])
            continue
        if existing["status"] != "open":
            existing["status"] = "open"
            existing["resolution"] = None
            existing["thread"].append({"author": "olmcp", "at": _now(), "body": "Marker present again; reopened."})
            result.reopened.append(existing["id"])
        if existing["anchor"].get("source") != new_anchor["source"] or (page and existing["anchor"].get("page") != new_anchor["page"]):
            existing["anchor"] = {**existing["anchor"], **{k: v for k, v in new_anchor.items() if v is not None}}
            if existing["id"] not in result.reopened:
                result.updated.append(existing["id"])
        store.save(existing)

    for c in store.all():
        origin = c.get("origin", {})
        if origin.get("type") == "marker" and c["status"] == "open" and origin["external_id"] not in present:
            c["status"] = "addressed"
            c["resolution"] = {"by": "marker-removed", "commit": commit, "note": "Marker removed from source.", "at": _now()}
            store.save(c)
            result.addressed.append(c["id"])
    return result


def _now() -> str:
    from .store import now

    return now()
