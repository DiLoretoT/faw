# The platform layer: official Microsoft skills

FAW governs the **process**: what gets verified, in what order, with what
evidence. It does not teach how to write an Eventstream or which API deploys a
semantic model, and it should not: that knowledge changes with every release, and
maintaining it by hand guarantees it ages badly without anyone noticing.

Microsoft maintains that layer in
[`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric):
operational skills per artifact type, written by the vendor, with decision trees
for which tool to use for each operation.

**The two layers complement each other because they solve different things.**
Microsoft's own repository describes itself as focused on artifact authoring, with
no formal gates and no data contracts. That is what FAW adds.

## Installation

It installs as a plugin, like FAW. There are **two separate bundles**: the Power
BI one is not included in the Fabric one.

```bash
claude plugin marketplace add microsoft/skills-for-fabric
claude plugin install fabric-skills@fabric-collection
claude plugin install powerbi-authoring@fabric-collection
```

It can also be consumed from a local clone of the repository, which is the route
for editors that do not support plugins. If a clone is used, declare its path in
`faw.json` under `channel.microsoft_skills`, and update it regularly: an outdated
platform skill is worse than no skill, because it states with confidence
something that stopped being true.

```bash
git -C <clone-path> pull --ff-only
```

## Which skill to read, and why there is no exhaustive table here

Microsoft reorganizes these skills between versions: bundles get merged, folders
get renamed, and skills that are no longer maintained get removed. A table of
paths copied into this file goes stale with nothing to warn about it, and the
method would end up sending the agent to read files that no longer exist.

**The index is read from the installed repository**, which is the only source that
does not age. The general orientation, which is stable across versions:

| Working on | Look for the skill covering |
|---|---|
| Spark notebooks, lakehouse | Spark |
| Semantic model: tables, measures, relationships, deployment, refresh | Semantic model authoring |
| Power BI report | Report planning, authoring, design and management (they are separate skills) |
| Warehouse, SQL | Warehouse and SQL database |
| Dataflows | Dataflows |
| Eventhouse, Eventstream, Activator | Each has its own |
| Version control integration | Git integration |
| Promotion between environments | Deployment pipelines |
| Per-environment parameters | Variable library |
| End-to-end medallion architecture | Medallion architecture |

Checked against the repository on 2026-08-19. If a path does not resolve, the
repository index wins over this table.

## The MCP servers it declares

The repository declares its own MCP servers for querying the SQL endpoint and the
Fabric catalog, and the Power BI bundle declares one for modeling. Before using
them, keep in mind the distinction Microsoft's own documentation makes:

- The **remote** Fabric and Power BI servers are meant for querying and for
  management operations, with their own authentication and audit logging.
- The **local** servers are the ones that can **write** a complete semantic model.
- The SQL endpoint is read-only by construction: it does not accept data
  modification.

Microsoft states explicitly that an autonomous or misconfigured MCP client can
perform destructive operations, and that the mechanisms to prevent it are not
standardized in the specification. That is why FAW puts its own gate over writes
through MCP (`faw/hooks/mcp_gate.py`) instead of trusting the server.

## Rules of coexistence

1. **FAW governs process; the Microsoft skills govern mechanics.** If one of them
   says "deploy straight to the workspace" and FAW says "through a pull request",
   FAW wins: those skills do not know the project's change channel or who reads
   each surface.
2. **No write operation a skill proposes is exempt from the approval of the
   turn.** The skill says *how*; the user gives the permission.
3. **Their tool decision trees are adopted.** That is exactly the kind of platform
   knowledge that is not worth maintaining separately.
4. **They are a source of mechanics, not of product behavior.** For a definitive
   statement such as "X cannot be done", principle 6 still applies: official
   documentation read, with the date of the page. A skill can be out of date like
   any other text.
5. **Never edit the files of the clone.** They are consumed as they are; anything
   that needs to change is handled on the FAW side.
