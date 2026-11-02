"""Comment store: one JSON file per comment under ``<review_dir>/comments/``.

One file per comment means concurrent additions never conflict in git.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import Config

SCHEMA = 1
STATUSES = {"open", "addressed", "resolved", "wontfix", "stale"}
_ID = re.compile(r"^C-(\d+)$")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.dir = cfg.comments_path

    def _path(self, cid: str) -> Path:
        return self.dir / f"{cid}.json"

    def all(self) -> list[dict]:
        if not self.dir.exists():
            return []
        items = []
        for p in sorted(self.dir.glob("C-*.json")):
            items.append(json.loads(p.read_text(encoding="utf-8")))
        return items

    def get(self, cid: str) -> dict:
        p = self._path(cid)
        if not p.exists():
            raise KeyError(f"no such comment: {cid}")
        return json.loads(p.read_text(encoding="utf-8"))

    def save(self, comment: dict) -> None:
        if comment.get("status") not in STATUSES:
            raise ValueError(f"invalid status {comment.get('status')!r}")
        self.dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(comment, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self._path(comment["id"]).write_text(text, encoding="utf-8")

    def next_id(self) -> str:
        nums = [int(m.group(1)) for p in (self.dir.glob("C-*.json") if self.dir.exists() else [])
                if (m := _ID.match(p.stem))]
        return f"C-{(max(nums) + 1 if nums else 1):04d}"

    def by_external(self, external_id: str) -> dict | None:
        for c in self.all():
            if c.get("origin", {}).get("external_id") == external_id:
                return c
        return None

    def new(self, *, body: str, author: str, origin: dict, anchor: dict, kind: str = "change-request") -> dict:
        comment = {
            "schema": SCHEMA,
            "id": self.next_id(),
            "kind": kind,
            "status": "open",
            "created": now(),
            "author": author,
            "body": body,
            "anchor": anchor,
            "thread": [],
            "resolution": None,
            "origin": origin,
        }
        self.save(comment)
        return comment

    def reply(self, cid: str, author: str, body: str) -> dict:
        c = self.get(cid)
        c["thread"].append({"author": author, "at": now(), "body": body})
        self.save(c)
        return c

    def set_status(self, cid: str, status: str, **resolution) -> dict:
        c = self.get(cid)
        c["status"] = status
        if resolution:
            c["resolution"] = {**(c.get("resolution") or {}), **resolution, "at": now()}
        elif status == "open":
            c["resolution"] = None
        self.save(c)
        return c
