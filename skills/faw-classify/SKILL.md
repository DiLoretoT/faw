---
name: faw-classify
description: Starts a piece of work under FAW. Classifies the request, assigns a tier, defines scope and opens the state. Use at the start of any data work on Fabric.
---

# Classify

Phase 1 of FAW. **Do not build anything yet.**

## What to do

1. **Restate the request in one sentence.** If the restatement does not come out
   obvious, ask before going further.

2. **Look at the real state**, not what you assume:
   - `python <faw>/scripts/state.py status`
   - `git status --porcelain` and the current branch
   - the artifacts the request touches: do they exist? do they have a contract?

3. **Assign a tier and justify it in one line:**

   | Tier | When |
   |---|---|
   | `QUESTION` | A question. No branch, no artifacts. |
   | `EXPLORATION` | Understanding something without touching it. Writing to the platform is forbidden. |
   | `MINOR-CHANGE` | A contained adjustment, without touching schema, business logic or the consumption layer. Around 30 lines. |
   | `ARTIFACT` | A table, notebook or pipeline, new or modified. |
   | `MODEL` | Semantic model: tables, relationships, measures, storage mode. |
   | `REPORT` | A Power BI report. **Requires a brief agreed with the user before building** (see below). |
   | `INCIDENT` | Something broken. |

   When in doubt between `MINOR-CHANGE` and `ARTIFACT`, it is `ARTIFACT`.

   **`MODEL` and `REPORT` are separate tiers because what a machine can verify is
   different in each.** In a semantic model, relationships, storage mode and
   column properties are read through an API and compared against what was
   declared. In a report, the layout and the choice of each visual are not
   verifiable that way, and development is iterative by nature. Charging a report
   the gates of a model would produce a gate impossible to satisfy honestly, and
   those should not exist.

4. **Define the scope: what is in and what is NOT.** The second part matters more;
   it is what stops the work from growing on its own.

5. **Branch**, if the tier needs one.

6. **If the tier is `REPORT`, classification includes the brief.** Building does not
   start without agreeing **with the user** what the report exists for. Objective,
   audience, the questions it has to answer, what is out of scope, the data source,
   and who validates the numbers. It is filled in at `docs/faw/<ticket>/brief.md`
   from `faw/contracts/TEMPLATE.brief.md`, and `scripts/verify_brief.py` checks it,
   rejecting an unfilled template. Inferring the scope by reading the semantic
   model **is not classifying**. It is writing the brief alone, without the
   conversation that validates it. The official report planning skill covers the
   mechanics of that conversation; read it first.

## Closing

Present it to the user, short:

```
Request  : <one sentence>
Tier     : <tier> - <one-line justification>
In       : <list>
Not in   : <list>
Branch   : <name>
Next     : <phase> - <the concrete action you will take there, not just the name>
```

**"Next" says which action follows, not only which phase comes** (principle 14).
"Next: PROFILING" is not enough; "Next: PROFILING, I am going to run a total count
against a distinct count on the candidate key and measure nulls per column" is.

**Wait for confirmation.** This is the one purely human gate of the method, and
that is deliberate. This is where how much process everything else will cost gets
decided.

With the approval:

```bash
python <faw>/scripts/state.py start --tier <TIER> --title "<title>" --artifact <type>
```

Pass `--ticket` when the project uses an external tracker, and `--context` when a
prior consultation already closed part of the design.

## Traps

- **Do not start building while classifying.** It is the most common deviation and
  the one that makes the rest of the method not apply.
- If the request is several things, classify them separately. One piece of work,
  one ticket.
- If while classifying as a `QUESTION` you realize something has to be touched,
  reclassify **before** touching it.
