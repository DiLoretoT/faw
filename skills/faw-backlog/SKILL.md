---
name: faw-backlog
description: Answers what to work on next and where a new request fits, against whichever ticket system the project uses or against the FAW internal registry. Use at the start of a working session or when what comes next is unclear.
---

# Backlog

Two questions: **what do I work on next?** and **where does this request fit?**

## Where the tickets come from

Declared by `tickets.system` in `faw.json` at the root of the repository. If the
file does not exist, the value is `internal`.

| System | Where they are read | How they are operated |
|---|---|---|
| `internal` | `docs/faw/tickets/*.md` in the repository | Read and edited as files; git provides the history |
| `ado`, `jira`, `github` | The declared tracker | Through its MCP server if connected in the session; if not, the user operates the tool and the work happens with whatever they report |
| `none` | There is no backlog | Work on what the user asks for at the time |

**Before reading an external tracker, check whether an MCP server is available for
it.** With MCP, read and update it directly. Without MCP, do not invent the state
of the backlog and do not assume a ticket exists: ask the user, or work with the
identifier they give.

A tool with no MCP server does not prevent using FAW. The only thing the method
needs from a ticket is its identifier.

## Mode: what do I work on next

1. **Get the real state.** From the declared tracker or the internal registry, not
   from memory or from what was discussed last session.

2. **Lay out the picture, short:**

   ```
   Open       : <N>
   In progress: <id> <title>
   Blocked    : <id> <title> - why
   Next       : <id> <title>   <- proposal
   ```

3. **Propose the next one ordered by technical dependency, not by backlog order.**
   Dimensions before facts, always; a table before the model that consumes it; the
   model before the report. Blocked work is not proposed: it is reported as
   blocked, with what would unblock it.

4. **Cross-check against the FAW state.** If `state.py status` shows open work, say
   so before proposing anything new. Opening a second piece of work without
   closing the first is how the thread gets lost.

5. **When proposing, say in one sentence what will be done if the user confirms**
   (principle 14). "Shall we start with 1001?" is not enough.

6. **If the backlog is empty**, say so rather than inventing work. That is the
   moment to offer `/faw-roadmap`: an empty backlog rarely means there is nothing
   to do, it means nobody has decided what comes next.

## Mode: where does this fit

A request that arrives through conversation is reconciled against what already
exists **before** creating anything:

| Situation | What happens |
|---|---|
| It is part of the scope of an existing ticket | Work happens in that ticket |
| It is new work | Propose creating the ticket, with its scope in one sentence |
| It is a question that touches nothing | Answer it; no ticket is opened |
| It contradicts something already decided | Say so explicitly before doing it |

**Never create or close a ticket without the user's approval**, neither in the
external tracker nor in the internal registry. A ticket created on your own
initiative pollutes a backlog somebody else owns.

## How the work is opened

With whichever identifier the declared system provides:

```bash
# External tracker: the identifier comes from there
python <faw>/scripts/state.py start --ticket 1001 --tier ARTIFACT --title "<title>"

# Internal registry: FAW generates the identifier and creates the ticket file
python <faw>/scripts/state.py start --tier ARTIFACT --title "<title>"
```

The `--artifact` parameter declares what is going to be built (`notebook`,
`semantic-model`, `report`, `pipeline`, `table`). It is used to know which official
platform skill applies, so pass it whenever it is known.
