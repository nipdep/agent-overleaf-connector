# Publishing (for the maintainer)

Where the package goes and how, in order. Steps 1 and 3 need your own accounts, so they are run by you, not by a tool.

**Do this first:** merge the documentation PR, then publish. npm shows the README that is *inside the tarball*, so
publishing before the merge puts the old README on the package page. A published npm version cannot be replaced, only
deprecated.

## 1. npm

One-time: create an account at npmjs.com, turn on 2FA, run `npm login`.

```bash
git checkout main && git pull
npm publish --dry-run --tag alpha      # runs the tests, lists the 18 files that would be uploaded
npm publish --tag alpha                # the real thing; --access public is already in package.json
```

- A prerelease must go under its own tag. `scripts/prepublish-check.js` (run by `npm publish`) refuses `1.0.0-alpha.N`
  without `--tag alpha`, and refuses a stable version under a prerelease tag, because npm would otherwise make the alpha
  the default `latest` that everyone installs.
- Users then install with `npm install -g olmcp@alpha`. A stable `1.0.0` is published with plain `npm publish`
  and becomes `latest`.
- Check it: `npm view olmcp dist-tags` and `https://www.npmjs.com/package/olmcp`.

## 2. Release bookkeeping

Bump `version` in `package.json` **and** in `server.json` (the top-level `version` and `packages[0].version`); the
regression test `npm and MCP Registry metadata agree with each other` fails if they differ. Add the changelog entry,
tag `vX.Y.Z` (tags cannot be pushed from the agent's sandbox, so you do it), and create a GitHub release.

## 3. MCP Registry (registry.modelcontextprotocol.io)

The registry stores metadata only and points at the npm package, so step 1 must be done first. Verified against the
registry's quickstart; the registry is in preview and its steps can change.

```bash
# install the publisher (macOS/Linux)
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/

cd agent-overleaf-connector            # the repo root, where server.json is
mcp-publisher validate                 # checks server.json
mcp-publisher login github             # follow the device-code link; sign in as nipdep
mcp-publisher publish
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.nipdep/agent-overleaf-connector"
```

How the pieces fit: `server.json` names the server `io.github.nipdep/agent-overleaf-connector`; `package.json` carries the
same string as `mcpName`, which is how the registry checks that you own the npm package; GitHub login ties the
`io.github.nipdep/` prefix to your account. Clients start the package as `olmcp mcp` (from `packageArguments`). An error
"Registry validation failed for package" means `mcpName` is missing from the *published* package, so publish to npm first
or after any change to it.

## 4. MCP directories (Smithery, Glama and similar)

Not verified: these sites were not reachable from the environment this guide was written in, so check each site's own
instructions. In general they list a server from its GitHub repository or its npm package, and read the README. Submit
`https://github.com/nipdep/agent-overleaf-connector` once the npm package and the README are final.

## Usage numbers

There is no telemetry in the tool, by design. Public signals: npm downloads
(`https://api.npmjs.org/downloads/point/last-week/olmcp`), GitHub stars, forks and Insights, Traffic, and issues.
