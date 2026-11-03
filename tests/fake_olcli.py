#!/usr/bin/env python3
"""A stand-in for ``olcli`` that follows its documented command shapes (aloth/olcli):

  olcli comments list [project] [--status s] [--context n] [--changes] [--json]   -> bare JSON array
  olcli comments reply <threadId> <body> [project] [--json]
  olcli comments resolve|reopen <threadId> [project] [--json]

State lives in the JSON file named by FAKE_OLCLI_STATE: {"threads": [ProjectComment, ...]} where a
ProjectComment has threadId, docId, path, position, line, column, selectedText, resolved, messages.
FAKE_OLCLI_FAIL=1 makes every call fail like an expired session.
"""
import json
import os
import sys

args = sys.argv[1:]
if os.environ.get("FAKE_OLCLI_FAIL"):
    print("Failed: session expired", file=sys.stderr)
    sys.exit(1)

state_path = os.environ["FAKE_OLCLI_STATE"]
state = json.load(open(state_path))
if args[:1] == ["edit"]:
    if os.environ.get("FAKE_OLCLI_EDIT_FAIL"):
        print("error: the old text was not found in " + args[2], file=sys.stderr)
        sys.exit(1)
    payload = json.loads(sys.stdin.read())
    state.setdefault("edits", []).append({"project": args[1], "file": args[2], "edits": payload["edits"]})
    json.dump(state, open(state_path, "w"))
    print(json.dumps({"path": args[2], "tracked": True, "applied": True, "changes": []}))
    sys.exit(0)
assert args[:1] == ["comments"], args
sub, rest = args[1], args[2:]

opts, pos, i = {}, [], 0
while i < len(rest):
    a = rest[i]
    if a in ("--status", "--context", "--concurrency", "--cookie"):
        opts[a] = rest[i + 1]
        i += 2
    elif a.startswith("--"):
        opts[a] = True
        i += 1
    else:
        pos.append(a)
        i += 1


def save():
    json.dump(state, open(state_path, "w"))


def find(tid):
    for t in state["threads"]:
        if t["threadId"] == tid:
            return t
    print(f"Failed: thread {tid} not found", file=sys.stderr)
    sys.exit(1)


if sub == "list":
    status = opts.get("--status", "all")
    items = [t for t in state["threads"]
             if status == "all" or (status == "open") == (not t.get("resolved"))]
    if "--json" in opts:
        print(json.dumps({"comments": items, "changes": []} if "--changes" in opts else items, indent=2))
    else:
        print(f"Found {len(items)} comment(s):")
elif sub == "reply":
    t = find(pos[0])
    msg = {"id": f"m{len(t['messages']) + 1}-fake", "content": pos[1], "timestamp": "2026-11-03T10:00:00Z",
           "user": {"email": "researcher@example.com"}}
    t["messages"].append(msg)
    save()
    print(json.dumps({"replied": True, "message": msg}))
elif sub in ("resolve", "reopen"):
    t = find(pos[0])
    t["resolved"] = sub == "resolve"
    save()
    print(json.dumps({"resolved" if sub == "resolve" else "reopened": True, "comment": t}))
else:
    print(f"Failed: unknown subcommand {sub}", file=sys.stderr)
    sys.exit(1)
