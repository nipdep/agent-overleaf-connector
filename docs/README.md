# Documentation

If this is your first visit, read the [main README](../README.md), then follow [Set up the connector](setup.md).

## Choose the guide for your task

| I want to… | Read |
|---|---|
| Install `olmcp` and make the first tracked edit | [Set up the connector](setup.md) |
| Understand proposals, follow-up revisions, tags, or new files | [Use `olmcp`](usage.md) |
| See exactly what the MCP can and cannot do | [MCP capabilities](usage.md#what-the-mcp-can-do) and [Safety boundaries](agents.md#security-and-trust) |
| Register Claude Code, Codex, or another MCP client | [Connect an AI agent](agents.md) |
| Test the alpha on a disposable project | [Alpha test plan](alpha-test-plan.md) |
| Check what has been verified or remains experimental | [Status and roadmap](status-and-roadmap.md) |
| Understand the implementation and design decisions | [Technical design](design.md) |

## Recommended reading order

1. [Setup](setup.md): install, authenticate, register the MCP, and choose a project.
2. [Usage](usage.md): the daily review loop and the meaning of a proposed edit.
3. [Agents and safety](agents.md): permissions, enforced limits, and the session-cookie trust boundary.

The other pages are reference material; you do not need them for normal use.

## Project history

The current program is the Node-only connector described in these pages. The earlier Python design is archived at [history/design-python.md](history/design-python.md), and its code remains on the [`python-legacy`](https://github.com/nipdep/agent-overleaf-connector/tree/python-legacy) branch.

Release-by-release changes are listed in the [changelog](../CHANGELOG.md).
