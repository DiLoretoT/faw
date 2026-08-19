---
name: faw-configure
description: Defines the project profile - ticket system, environments, available channels - and writes it to faw.json. Use the first time FAW is activated in a repository, or when that infrastructure changes.
---

# Configure the project

FAW works without this configuration. What changes is how much it has to assume.

With no profile, the method resolves every missing value by the strictest option:
it assumes there is a single environment and that it is production, so every write
to the platform requires authorization in writing before it runs. That is correct
as a default -- being wrong on the strict side costs one extra authorization,
being wrong on the other side writes to production without asking -- but it can be
more ceremony than the project needs.

This skill asks the questions once and writes `faw.json` at the root of the
repository.

## Look before asking

Several answers can be inferred from the repository rather than asked. Infer,
propose, and confirm; do not ask what is already visible:

- The git remote says whether the project lives on GitHub or Azure DevOps, which
  is a hint about where the tickets are.
- The MCP servers connected in the session say which trackers can be operated
  directly.
- The repository structure usually shows whether platform artifacts are versioned.

## The questions

**1. Where do the tickets live?**

Options: `ado`, `jira`, `github`, `internal`, `none`.

If the user uses no tracking tool, or does not want to connect one, the answer is
`internal`: FAW keeps the registry under `docs/faw/tickets/`, generates the
identifiers, and git provides the history. Nothing has to be installed and no
identifiers have to be invented.

Whether an MCP server exists for the chosen tool is a separate matter and does not
change the answer. With MCP the agent reads and updates the tickets; without MCP
the user operates their tool and the method uses the identifier they report.
Either way FAW works the same.

**2. Is there a development environment separate from production?**

This is the question that changes behavior the most. A single workspace is a valid
and supported pattern -- Microsoft documents it for smaller organizations -- but
it means everything written lands on data someone is using.

- **There is a separate environment**: authorization to write is agreed in
  conversation during the turn.
- **There is only one**: every write to the platform requires the reason to be
  written to `.faw/tenant-authorization.txt` before it runs. The file is consumed
  when used.

**3. How does a change reach production?**

`deployment-pipeline`, `git`, `manual` or `none`. Deployment pipelines need
several workspaces in the same capacity, so they are not available in a
single-workspace deployment.

**4. Is code executed against the platform from here?**

If the project uses interactive Spark sessions, declare it. Without that
declaration the agent does not assume that channel is available. It proposes it
and the user decides.

**5. Is there a control table for runs?**

If one exists, declare its name and every execution that writes gets recorded
there. If not, the record goes to the ticket receipt.

## The file that gets written

```json
{
  "tickets": { "system": "internal" },
  "environments": { "dev": false, "prd": true, "promotion": "manual" },
  "channel": { "livy": false, "control_table": null }
}
```

`faw.json` **is versioned**. These are the team's process rules. They have to
travel with the repository, be reviewed in a pull request, and be the same for
everyone. A profile that lives on a single machine produces two people working
under different rules with nothing to detect it.

## What does not go in that file

Names of people, identifiers of other projects, and local paths go in
`.faw/config.json`, which is not versioned:

```json
{
  "client_people": ["Surname"],
  "internal_literals": ["internal-repo"],
  "artifacts_in": "/path/to/internal/documentation"
}
```

The two lists feed the surface gate, which stops a commit or a pull request that
contains them. `artifacts_in` is used when the design reasoning should not stay in
a repository a third party reads.

## When finishing

Show the file that was written and what changes in practice, in two or three
lines. If the project already had a `faw.json`, state explicitly which values are
changing before writing it. Changing the profile in the middle of open work alters
the rules that work started under.
