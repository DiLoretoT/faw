# The phases, operationally

What the agent does in each one, what it produces, and what has to be true to
close it.

---

## 1. CLASSIFICATION

**Goal:** understand the request, assign a tier, and not start building what was
not asked for.

What happens:
1. Restate the request in one sentence. If the restatement is not obvious, ask
   before going further.
2. Look at the real state: current branch, working tree, the last transitions in
   `.faw/state.jsonl`, the artifacts the request touches.
3. Assign a tier and **justify it in one line**.
4. Define the scope explicitly: what is in and **what is not**.
5. Create a branch if the tier needs one.

Produced: the classification, in the conversation. No document, except the ticket
when the project uses the internal registry.

**Where the work identifier comes from.** Declared by `tickets.system` in
`faw.json`. With an external tracker the identifier comes from there and is passed
with `--ticket`; with the internal registry FAW generates it and creates the
ticket file under `docs/faw/tickets/`. Whether the external tracker has an MCP
server connected changes who operates it, not the method. With MCP the agent
reads and updates it; without MCP the user operates their tool and reports the
identifier.

**When the request is not enough to classify properly.** If the source is not
understood, a business definition is missing, or a platform decision depends on
data nobody has measured, do not push forward on assumptions. Offer the user a
**prior consultation**: a `QUESTION` tier piece of work scoped to answering
exactly those doubts, producing a document under `docs/faw/consultations/`. That
document is then passed when the real work is opened:

```bash
python <faw>/scripts/state.py start --tier ARTIFACT --title "..." \
    --context docs/faw/consultations/<id>.md
```

When the real work opens, **do not ask again what the user has already
answered**. Restate in one line what was decided and ask only for what is new.

**Closing, checkpoint 1 of 3:** the user confirms tier and scope. This is where
how much process the rest will cost gets decided.

**If the tier is `REPORT`, classification includes the brief.** Building a report
does not start without agreeing **with the user** what it exists for. Objective,
audience, the questions it has to answer, what is out of scope, the data source,
and who validates the numbers. It is filled in at `docs/faw/<ticket>/brief.md`
from `faw/contracts/TEMPLATE.brief.md`, and `scripts/verify_brief.py` checks it.
Inferring the scope by reading the semantic model is not classifying. It is
writing the brief alone, without the conversation that validates it. The official
report planning skill covers the mechanics of that conversation; read it first.

---

## 2. PROFILING

**Goal:** make the design rest on numbers rather than assumptions.

What happens, depending on what the request touches:

**Source (a new table, or an entity not profiled before)**
- Total rows.
- Candidate natural key: total count against distinct count. If they do not
  match, it is not the key, and discriminators have to be found.
- For every column the target layer will consume: nulls, distinct values, minimum
  and maximum.
- Sentinel values in the source and how often they actually appear.
- Real types, not the ones in the specification.

**Existing curated layer (`MODEL` and `REPORT` tiers)**
- Rows and columns of every table the model will consume.
- Business totals the report is supposed to reproduce.
- Distribution of the dimensions that will be used for slicing.

**Symptom (`INCIDENT` tier)**
- What was expected, what was obtained, since when.
- History of the artifact: last write, last schema change.

Produced: `docs/faw/<ticket>/profiling.md`, with **every number accompanied by the
query that produced it**.

**Closing, the `profile` gate, without stopping.** The receipt exists and contains
queries, not only results. The agent shows the receipt and continues straight to
DESIGN. This is not a checkpoint, it is automatic passage.

> Profiling is read-only. If something has to be written in order to profile,
> principle 3 applies: explicit authorization.

---

## 3. DESIGN

**Goal:** decide before building, and write the decisions down in a form a
machine can verify later.

What happens:
1. **Grain.** One sentence: "one row per ___". If it cannot be written that way,
   the grain has not been decided.
2. **Natural key**, the one verified during profiling.
3. **Data contract** at `<artifact root>/contracts/<schema>.<table>.yml`: columns,
   types, nullability, foreign keys, quality rules. See below for what the
   artifact root is.
4. **Where each transformation lives.** The criterion: *if deleting today's
   consumer makes the transformation pointless, it does not belong in the layer
   below.*
5. **The architecture decisions this work would leave settled.** Which ones apply
   depends on what is being built: storage mode of the semantic model, grain,
   where each derived calculation is resolved, load strategy, naming convention.
   They are raised and justified **even when the user did not mention them and
   does not know the topic**, because the consequence of getting them wrong gets
   paid either way, and a default nobody chose is a decision the tool made. Every
   definitive statement about the platform is backed by documentation that was
   read, with its date. Detail in the `faw-design` skill.
6. **Risks.** What can go wrong and how it will be detected. This is not
   ceremony. Each risk becomes an assertion or a diagnostic metric in the
   artifact.
7. **Impact.** What breaks if this changes: downstream artifacts, semantic
   models, reports.

Produced. The contract and `<artifact root>/faw/<ticket>/design.md`.

### The artifact root is the user's decision

Contracts, profiling receipts and design documents contain long reasoning,
discarded alternatives, open findings and business questions. By default they live
in the working repository, under `contracts/` and `docs/faw/<ticket>/`, and the
`surface` gate does not inspect those paths. They are artifacts of the method
itself.

That is only correct if whoever reads the repository can read that reasoning. When
they cannot -- the repository lives in a client's organization, or a third party
reads it who should not see internal work -- the root is declared outside the
repository in `.faw/config.json`, which is not versioned:

```json
{
  "artifacts_in": "/path/to/internal/documentation/FAW",
  "client_people": ["Surname"],
  "internal_literals": ["internal-repo", "OtherClient"]
}
```

FAW does not infer whose repository this is. It treats them all the same, as
surface a third party reads (see [`client-surface.md`](client-surface.md)), and
the user declares what must not leak. `client_people` and `internal_literals` feed
the `surface` gate, which stops the commit or the pull request that names a person
or a declared internal literal. Both lists are empty by default.

Leaving the artifacts in the repository without thinking about it publishes
internal work where the reader of the repository sees it. That is why the path is
declared explicitly when that reader should not.

**Closing, checkpoint 2 of 3:** the contract exists, is syntactically valid,
declares grain, key and columns, **and the user confirms the design before
building**. Not only for the first artifact in a new domain. Always, in `ARTIFACT`
and `MODEL`. This is where a wrong decision costs the least.

---

## 4. BUILD

**Goal:** implement it and show that it runs against real data.

What happens:
0. Check which official platform skills or tools are available in the session and
   state which one is being used, or why none of them applies. Do not assume the
   catalog from memory. The vendor reorganizes it between releases. Detail in
   [`microsoft-skills.md`](microsoft-skills.md).
1. Implement the artifact.
2. **Validations go inside the artifact**, not in a separate script: natural key
   assertion, schema guard, diagnostic metrics. They have to run on every future
   execution, not only today.
3. Run it against the environment, with explicit authorization if it writes.
4. Report rows **and** columns, and the result of the assertions.

Produced. The code, and the table or artifact written to the environment.

**Closing, the `assertions`, `authorization` and `tooling` gates, without stopping
as a process step.** They ran and passed, there was explicit approval for each
write, and the platform tooling used is stated. The approval for a write is asked
every time, at the moment of writing; it is not the phase checkpoint.

> If the artifact changes the schema of an existing table, the migration is a
> separate decision, declared and authorized separately. It is not part of
> "running the notebook".

---

## 5. VALIDATION

**Goal:** have someone who did not build it look for the error instead of
confirming the success.

Run by the [`faw-validator`](../../agents/faw-validator.md) agent, with the
contract and the profiling receipt as input, **without the reasoning behind the
build**.

It checks:
1. **Schema against contract**, with `scripts/verify_contract.py`. Column by
   column.
2. **Numbers against profiling.** Is the artifact count consistent with what was
   measured at the source? If it differs, is that explained by a filter declared
   in the design?
3. **Quality rules from the contract**: nulls, uniqueness, domains.
4. **Semantic model**, where it applies, with `scripts/verify_model.py`:
   relationships, storage mode, summarization and sort properties.
5. **Open findings**, with their impact.

Produced: `docs/faw/<ticket>/validation.md` with a verdict of **PASS** or **FAIL**.

**Closing, checkpoint 3 of 3:** the `schema` gate and, where it applies, the
`model` gate, **and the user sees the verdict and confirms before publishing.**

> If it fails, the work returns to BUILD. **It is not patched here.** The patch
> would be written by the validator, and then nobody would be left looking from
> the outside.

---

## 6. PUBLICATION

**Goal:** get what was built to its destination without taking anything down on
the way.

What happens:
1. **Check the complete diff** with `scripts/verify_diff.py`. It fails if
   protected metadata is touched without declaring it.
2. Commit and push on the branch.
3. Pull request, following [`client-surface.md`](client-surface.md).
4. Merge.
5. **Sync the workspace** and check the state after deployment: do the artifacts
   keep their default lakehouse? Is there a phantom diff? If there is one and it
   is only formatting, commit it and close the cycle.
6. Update the project tracker with the exact resume point.

**Closing, the `git-clean` and `metadata` gates.**

> Publication cannot be left by abandoning. Nothing is left to decide here, only
> steps left to finish: leaving is closing, and it owes its gates.

---

## Leaving

From any phase except publication, work can be **abandoned** or **paused**. Which
one has to be stated.

- **Pausing** records the exact phase and the resume point. Resuming re-enters
  that phase.
- **Abandoning** records why. The reasoning stays on the branch even if the work
  does not continue.

Stepping away is allowed. Doing it silently is not.
