# Installation

## Requirements

- A recent version of Claude Code. The MCP gate uses matchers over tool names, so
  a version that supports matching MCP tools in `PreToolUse` is needed.
- Python 3.10 or later on the PATH
- `pip install pyyaml`
- git on the PATH

## 1. Load the plugin

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

It installs at user level and loads in every session. It is a copy. It lives in the
plugin cache, so a change in the source repository does not apply until it is
updated.

```bash
claude plugin update faw@faw
```

To develop FAW itself, or to try it without installing, it can be loaded from a
local clone for a single session:

```bash
claude --plugin-dir <clone-path>
claude plugin validate <clone-path>
```

With the plugin installed, the hooks, the `/faw:*` skills and the validator
agent are registered with no further steps.

## 2. Activate FAW in a project

The hooks are opt-in per project. They do nothing unless the repository has a
`.faw/` directory at its root.

```bash
mkdir .faw
```

From that moment. Every turn receives the method state; the first write with no
classified work is denied; commits pass through the metadata, platform and surface
gates; pull requests pass through the client-surface checklist; and writes to the
platform through MCP servers are subject to the current phase.

When the working folder is a git repository, add `.faw/` to its `.gitignore`. The
state, the receipts and the configuration are artifacts of the method, and the
configuration can contain names that should not be published. In a folder without
git there is nothing to ignore.

## 3. Configure the project

```
/faw:configure
```

It defines where the tickets live, whether there is a development environment
separate from production, and which execution channels are available. The result
is written to `.faw/config.json`, next to the state and the receipts. One local
file holds the whole project declaration, including the two lists the surface
gate reads.

```json
{
  "tickets": { "system": "internal" },
  "environments": { "dev": false, "prd": true, "promotion": "manual" },
  "channel": { "livy": false, "control_table": null },
  "client_people": [],
  "internal_literals": []
}
```

Everything is optional. Without this file the method still works, resolving every
missing value by the strictest option: a single environment, treated as
production, with authorization in writing before each write.

The file is local by design and never published, so nothing about FAW appears in
anything a third party reads. `client_people` and `internal_literals` feed the
surface gate, which stops a commit or pull request that contains them.

## 4. The Microsoft platform layer

FAW governs the process and leaves the mechanics of each artifact to the official
skills, which install separately. There are two bundles. The Power BI one is not
included in the Fabric one.

```bash
claude plugin marketplace add microsoft/skills-for-fabric
claude plugin install fabric-skills@fabric-collection
claude plugin install powerbi-authoring@fabric-collection
```

Detail and rules of coexistence in
[`faw/rules/microsoft-skills.md`](../faw/rules/microsoft-skills.md).

## Check that it works

```bash
# 1. The per-turn injection answers for an activated project:
echo '{"cwd":"/path/to/project"}' | python <faw>/faw/hooks/inject_context.py

# 2. The verifiers have not broken over time:
python <faw>/scripts/self_check.py

# 3. The real test: ask Claude for a write with no classified work.
#    It has to be denied, citing the classification.
```

The third one is what matters. A hook that breaks exits with a non-zero code, and
that is treated as non-blocking, so a broken hook looks exactly like a hook that
approved the action. They get tested by running them.

## Single-use permissions

When a gate blocks something intentional, the release is a file that is consumed
when used, so a one-off exception does not become a standing permission nobody
remembers granting.

| Gate | File |
|---|---|
| `metadata` | `.faw/metadata-allowed.txt` with the reason |
| `platform` | `.faw/platform-allowed.txt` with the reason |
| `surface` | `.faw/surface-allowed.txt` with the reason |
| Writes to the platform, in single-environment projects | `.faw/tenant-authorization.txt` with the operation and the reason |

The hooks run **before** the command, so writing the file and performing the action
in the same call does not work. When the hook looks, the file does not exist yet. It
takes two steps.

## The limits

Arbitrary code running inside a Spark session cannot be inspected before it runs,
and files written from the shell through redirection or a heredoc do not pass
through the write hook. There the method detects and does not prevent. A method that
promised to block them would be lying about a gate.

## Uninstall

- Deactivate it in a project: delete `.faw/`, and the hooks go back to doing
  nothing.
- Remove the plugin: `claude plugin uninstall faw`.
