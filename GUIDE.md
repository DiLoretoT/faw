# FAW — Complete guide

Reference document for the method. It explains what problem it solves, how it is
built, and how it is operated. The rules the agent loads on every turn live
separately, in [`faw/rules/`](faw/rules/).

---

## 1. The problem

How a data change gets built depends on the session it was built in. Context falls
behind. What was agreed on Monday is not loaded on Wednesday. Some days the source
gets checked before the table is written, and some days it does not. The same task,
done twice a week apart, takes two different paths, and neither leaves a record of
why.

That variability is what FAW addresses. It does not promise to save time; it
reduces the surface where an error passes without anyone reviewing it.

The reason it matters more here than in application development is what a data
artifact is. In software, a wrong result usually has a test that can express it. A
function is given inputs and its output is compared against what it should be. In
data work, **the correct result is not verifiable by the code**. No test knows
whether 2,705 rows is the number that should have come out. That is only known by
measuring against the source, and only if somebody measures.

Four concrete ways this shows up:

- A dimension gets published with eleven of the twenty-three columns its contract
  declares. Validation checked that the row count matched, and it did.
- Three relationships of a semantic model point at the same column of the fact
  table, because a dialog offered a default three times. The model publishes with
  no error and returns plausible totals.
- A commit described as formatting also drops the default lakehouse assignment of
  several notebooks. The diff shown on screen did not reach the file header.
- Date foreign keys are left null. The affected rows disappear from the total as
  soon as someone filters by date, with no error message.

None of these is caught by a unit test, a linter or a code review. FAW exists so
that the measurement that does catch them is not left to memory.

The idea that orders the rest: **evidence before assertion**. A number without the
query that produced it is not data, it is an opinion in the shape of data.

---

## 2. How it is built

The method has three layers, and the difference between them determines what
happens when something is not followed.

**The rules** are text the agent reads. They live in `faw/rules/` and describe what
to do in each phase, which principles always apply, and what content can reach each
surface. Their force depends entirely on the agent reading and applying them.

**The gates** are verifiers that check a specific fact and issue a signed receipt.
The state machine recomputes that receipt before allowing a phase change, so an
unsatisfied gate stops the work. A data contract that does not match the real table
is not a warning. It is a phase that does not advance.

**The hooks** are programs that run before an action and can deny it. They run
outside the model, so they do not depend on the agent choosing to invoke them. An
attempt to edit a file without having classified the work is denied before the file
is touched.

The reason for having all three is that they cover different surfaces. A hook can
stop a write but cannot tell whether a number is correct. A gate can verify a
schema but only when someone runs it. A written rule can describe judgment, which
neither of the other two does.

What the method does not do is pretend the three are equivalent. Every gate declares
its strength, and every principle says whether a gate, a hook or only its reading
backs it. A gate presented as stronger than it is turns the rest into suggestions.

---

## 3. The seven classifications

The first thing that happens to any request is that it gets a tier. The tier
determines how much process that work pays, and it exists so a three-line
adjustment does not cost the same as a new semantic model.

| Tier | What it is | Route |
|---|---|---|
| **QUESTION** | A question that touches nothing | Does not enter the graph |
| **EXPLORATION** | Understanding something without modifying it | Classification, profiling, a document |
| **MINOR-CHANGE** | A contained adjustment | Classification, build, publication |
| **OPERATION** | Running what already exists | Classification, execution |
| **ARTIFACT** | A table, notebook or pipeline | The six phases |
| **MODEL** | A semantic model | The six, verified through its definition |
| **REPORT** | A report | Agreed brief, build, publication |
| **INCIDENT** | Something broken | Fast lane with a measured diagnosis |

`MODEL` and `REPORT` are separate because what a machine can verify differs. In a
semantic model, relationships, storage mode and column properties are read through
an API and compared against what was declared. In a report, the layout and the
choice of each visual are not verifiable that way, and development is iterative by
nature. Charging a report the gates of a model would create a gate impossible to
satisfy honestly, and those should not exist.

`MINOR-CHANGE` has an explicit guardrail. If the change touches schema, business
logic or the consumption layer, or exceeds roughly thirty lines, it gets
reclassified to `ARTIFACT`. This is not left to judgment in the moment.

`OPERATION` covers running existing artifacts without changing their definition. A
backfill, a rerun of a failed pipeline, an on-demand refresh. None of that is
building, and forcing it through six phases would push people to skip the method
exactly when they touch production data. It pays one checkpoint, where what runs,
against what, and the expected delta get agreed, and it closes by comparing the
real delta against the expected one. Changing code or schema reclassifies;
diagnosing something broken is an `INCIDENT`.

`QUESTION` does not enter the state machine. It opens no ticket and touches no
state file. Putting it inside would be the kind of ceremony that makes a method get
abandoned. The graph still defines a QUESTION route as an escape hatch: if one is
opened anyway, it closes straight back to idle.

---

## 4. The phases and the graph

`faw/transitions.json` defines a directed graph. The nodes are the phases plus an
idle state; the edges are the allowed moves; each edge can require gates to cross.

That it is a graph and not a list of rules has a practical consequence. From build
you can only go to validation, never jump straight to publication. The jump is not
forbidden by a warning, it does not exist as an edge.

```
ARTIFACT / MODEL:
  CLASSIFICATION → PROFILING → DESIGN → BUILD → VALIDATION → PUBLICATION → IDLE
       ▲(1)                     ▲(2)              │   ▲(3)
       └── confirmation ────────┘        on failure└───┘ back to BUILD

MINOR-CHANGE:
  CLASSIFICATION ──────────────────────► BUILD ──────► PUBLICATION → IDLE

REPORT:
  CLASSIFICATION ──brief──► BUILD ─────────────────► PUBLICATION → IDLE

OPERATION:
  CLASSIFICATION ──scope──► EXECUTION ──delta──► IDLE
```

The tiers are different paths over the same graph, not separate graphs.
`scripts/state.py` walks it. It checks which node the work is on, whether the
requested edge exists for the active tier, and whether its gates are satisfied.
When any of that fails, it rejects the transition.

### What each phase does

**Classification.** Restate the request in one sentence, look at the real state of
the repository, assign a tier, and define explicitly what is out of scope. Nothing
gets built. It closes with the user's confirmation.

**Profiling.** Measure the source. Every number reported comes with the query that
produced it, and the natural key is proven by querying the table rather than copied
from a specification. This is a read-only phase, and the write hook enforces it:
during profiling any edit other than the receipt itself is denied.

**Design.** Grain in one sentence, verified natural key, data contract, and the
architecture decisions that are expensive to reverse. It closes with the user's
confirmation before building.

**Build.** Implemented with the validations inside the artifact rather than in a
separate script, so they run on every future execution and not only the first time.
Rows and columns get reported, never rows alone. Which official platform tooling
was used gets stated.

**Execution.** Only in the operation tier. Runs what was scoped, with the write
authorization asked at the moment of writing, and closes by comparing the real
delta against the expected one.

**Validation.** Run by an agent that did not build, instructed to refute rather
than confirm. If it fails, the work returns to build. It is not patched here,
because the patch would be written by whoever is validating and nobody would be
left looking from the outside.

**Publication.** Check the complete diff, commit, pull request, sync the
environment and check the state after deployment.

---

## 5. The checkpoints

The process stops and waits for the user at exactly three moments, and they are few
on purpose. A method that asks all the time teaches people to answer yes without
reading.

1. **Before profiling**: the tier and the scope are agreed.
2. **Before building**: the grain, the key and the architecture decisions are
   agreed. This is where a wrong decision costs the least.
3. **Before publishing**: the verdict is agreed.

The shorter tiers keep fewer stops. An operation has a single one, before
anything runs.

They are stated by what comes next rather than by what just finished, because what
the user is approving is what happens after they say yes.

Every closing question says what will be done if the user confirms, not only which
phase comes next. "Shall I move to profiling?" makes someone approve a phase in the
abstract; "I am going to compare the total row count against the distinct key count
and measure nulls per column, shall I go ahead?" makes them approve something
concrete, and lets the deviation show before it happens.

---

## 6. The gates and their strength

Every gate declares what backs it. The scale is honest because otherwise it would
be useless:

| Strength | What backs it | How it can be lied to |
|---|---|---|
| **machine** | A script checks the fact and issues a receipt that gets recomputed | Not without modifying the verifier |
| **receipt** | A document exists with sufficient content | With a filler file |
| **declaration** | The agent states that it was done | By saying so |

The main ones:

| Gate | What it verifies | Strength |
|---|---|---|
| `contract` / `schema` | Every column of the real table against the declared contract | machine |
| `model` | Relationships, storage mode and properties of the semantic model | machine |
| `metadata` | That the diff does not alter protected configuration without declaring it | machine |
| `platform` | That platform syntax literals have precedent or resolve | machine |
| `git-clean` | That no uncommitted changes remain when closing | machine |
| `brief` | That the report brief has content and is not the template | machine |
| `profile` | That the profiling receipt exists and belongs to the open ticket | receipt |
| `tooling` | Which official platform tooling was used, or why none applied | declaration |
| `user_confirmation` | That the user approved | declaration |
| `authorization` | That there is permission to write to the platform | declaration, or hook |

### The receipts

A verifier that passes issues a receipt with the hash of what it checked. The state
machine recomputes those hashes before allowing the move, so a receipt issued over
an earlier version of the file no longer counts. Without this, "I already verified
it" would be a claim about the past that cannot be checked.

Gates that work table by table issue one receipt per table. When a ticket covers
several, the scope is declared on the move and the gate requires the receipt of each
one. Without that declaration, a nine-table ticket could close the phase having
verified only the last.

---

## 7. Where Claude stands, and the project profile

Work on a data platform happens in three different places, and telling them apart
is what makes the rest of this section simple.

The **tenant** is where the artifacts run. The **repository that backs the
workspace**, when git integration is on, is often synced on the service side
without anyone cloning it. And the **working folder** is wherever Claude Code is
standing. A local path on the engineer's machine, git or not, and usually not the
backing repository.

**You do not need to stand in the repository that backs the workspace.** The
working folder is any local path. When it happens to be a git repository, the
commit and pull request gates act on it; when it is not, the gates that need git
say so and step aside instead of failing.

The profile describes what FAW cannot know about the project and should not
assume. Where the tickets live, whether a development environment exists separate
from production, whether code gets executed against the platform. It lives in
`.faw/config.json`, in the working folder, next to the state and the receipts.
Local by design, so nothing about FAW has to appear in anything a third party
reads.

```json
{
  "tickets": { "system": "internal" },
  "environments": { "dev": false, "prd": true, "promotion": "manual" },
  "channel": { "livy": false, "control_table": null },
  "client_people": [],
  "internal_literals": []
}
```

Everything is optional. What matters is how the missing values get resolved.

### The defaults are the strict ones

A missing value is resolved by the option that asks for more control, never by
the one that allows more. With no environments declared, the method assumes there
is one and that it is production, so every write to the platform requires the
reason in writing before it runs.

The asymmetry of the error justifies it. A stricter value costs an authorization
the user was going to give anyway; a looser one writes to production without
asking.

That default is not pessimism. Microsoft documents deployment on a single
workspace as a valid, supported pattern for smaller organizations, and in that
pattern deployment pipelines do not exist because they need several workspaces. A
project without a separate development environment is a normal case.

### Every key has a consequence

A key that only produced different wording would not be in the file.
`environments.dev` decides whether the authorization to write is spoken or has to
be written down before running. `tickets.system` decides where the work
identifier comes from and whether there is an external backlog to read. The same
file carries `client_people` and `internal_literals`, the two lists the surface
gate reads.

---

## 8. The tickets

The method needs a work identifier to name its receipts and to make "where were we"
answerable after the session closes. That identifier usually comes from an external
tracker, but requiring one would turn a project management tool into an installation
prerequisite.

There are three situations and all three work equally well:

**The project uses a tracker with an MCP server connected.** The agent reads the
backlog and updates the tickets directly. The identifier comes from there.

**The project uses a tracker without MCP**, or with the connection deliberately
disabled. The identifier still comes from there, but the user reports it and
operates their own tool. The method does not invent the state of the backlog or
assume a ticket exists.

**The project uses no tracker.** FAW keeps the registry in `docs/faw/tickets/`,
generates sequential identifiers and creates the ticket file when the work opens.
When the folder is under git, the file history shows how each scope changed; without git, the log section inside each ticket carries the trail.

Tickets in the internal registry are versioned and **pass through the surface
gate**, unlike the rest of the method's artifacts. A ticket contains open questions
and tasks assigned to people by its nature, which is exactly the content that should
not reach a repository a third party reads.

---

## 9. The change channel

The everyday question is which route each modification takes. A pull request, an
interactive execution against the platform, or the product interface. The criterion
that answers it: **the channel is decided by where the record has to end up.**

| What | Channel | Authorization | Record |
|---|---|---|---|
| Notebook, pipeline code, contract, documentation | Git and pull request | On merge | The commit |
| Reading data, profiling, diagnosing | Direct query | None, it is a read | The profiling receipt |
| Writing or deleting a table | Execution against the platform | Explicit, with table, operation and rows | The receipt, and the control table if one exists |
| Pipeline canvas, permissions, shortcuts | Product interface | On commit | The commit of the environment |
| Semantic model, report | Interface or desktop tool | On commit | The commit and its verifier |
| Anything in production | The declared promotion mechanism | Explicit, always | The deployment history |

None of this table requires the backing repository to be the working folder. The
pull request can be created from anywhere with the CLI, and the workspace sync is
the platform's own mechanism.

Two rules follow. First. Every write made by direct execution has to be
**reproducible from a versioned artifact**. If the logic that produced it only
existed inside a session that is now closed, that is not a change, it is an accident
nobody can reproduce. Second. Git is the source of truth for everything
serializable, and the deployed environment is a destination, not a place to edit.

### What can be blocked, and what cannot

Writes that go through MCP server tools **are** covered. Those tools are presented
to hooks like any other, named `mcp__server__tool`, so a hook intercepts them before
they run. The hook distinguishes reads from writes and, when in doubt, classifies as
a write. Being wrong on the strict side costs an unnecessary authorization; on the
other side it lets a write through unchecked.

This matters more than it sounds, because without it the phases governed the code
and not the data. You could be in profiling, which is read-only by definition, and
write to the platform with nothing noticing.

Microsoft's documentation for its MCP servers warns that an autonomous or
misconfigured client can perform destructive operations, and that the mechanisms to
prevent it are not standardized in the specification. That is the reason for putting
the safeguard in the orchestrator rather than trusting the server.

**What cannot be blocked.** Arbitrary code running inside a Spark
session, and files written from the shell through redirection or a heredoc. No hook
can inspect those before they happen. There the method detects and does not prevent,
and promising otherwise would be lying about a gate.

---

## 10. Client surface

Before writing anywhere, ask who reads it.

FAW does not distinguish own repositories from client repositories. Every governed
repository is treated as surface a third party reads, and every commit and pull
request is written accordingly. The distinction is deliberately absent. It is a
decision made once, which removes the chance of getting it wrong project by project.

The failure this closes. A remote repository feels like an internal workspace and is
not. Design reasoning, open findings and tasks assigned to people end up published
where the wrong person reads them, with nothing checking.

What never goes. Referring to the client in the third person, assigning tasks to
their people, unresolved business findings, discarded alternatives with their full
reasoning, internal methodology, and AI attribution. What does go in a pull request
is what changed, one line of rationale per non-obvious decision, the validation
numbers, and a deployment note when a manual step is needed.

What is specific to each project, such as names of people or identifiers of other
projects, is declared in `.faw/config.json`, and the gate stops the commit or pull
request that contains it. Detail in [`faw/rules/client-surface.md`](faw/rules/client-surface.md).

---

## 11. The principles

Fourteen rules that do not depend on the tier or the phase. They live in
[`faw/rules/00-principles.md`](faw/rules/00-principles.md), which the agent reads
when opening a piece of work, and the context hook restates the ones governing the
current phase on every turn.

Every principle declares what backs it: a gate, a hook, or only its reading. The
ones that depend on reading are the ones that depend on the agent's judgment, and
that is marked rather than disguised. A principle presented as a guarantee with
nothing enforcing it would be exactly the failure the method exists to prevent.

The fourteen, one line each. Evidence before assertion; validate the schema and not
just the count; explicit authorization per turn to write; between failing and
returning a doubtful number, fail; resolve derived values as far upstream as the
design allows; statements about the platform need documentation that was read and
dated; know who reads each surface; do not fight the serializer; reproducing code by
hand is dangerous; a job reporting success is not evidence; verify against the real
environment and not against the code; a relationship that publishes without error is
not verified; the phase is declared in every reply; no closing question without
saying what comes next.

---

## 12. The decisions that get made on their own

Every artifact that gets built leaves architecture decisions settled, whether they
were discussed or not. When they are not, they get made by the default value of a
dialog, the habit of the previous project, or the first path that appeared. They are
still decisions; what changes is that nobody can explain why they were made or what
was ruled out.

The method does not handle this with a list of mandatory topics. It handles it with
a question the design phase requires: **which decisions will this work settle, and
which of them has the user not discussed.** The ones that surface get put on the
table; the user then decides whether to review them or stay with the default. What
must not happen is finding out once it is expensive to reverse.

The criterion for which ones to surface. If changing it three months from now would
mean rebuilding something, raise it now; if it is reversible with a commit, it does
not need the conversation.

That review gets offered even when the user did not ask and does not know the topic,
because the consequence of getting it wrong gets paid either way. When they have no
formed opinion, do not choose silently and do not lecture. Explain what each option
implies for that specific case, recommend one with its rationale, and move on.

Where they tend to hide, as orientation rather than a checklist. The storage mode of
the semantic model, the grain of each fact table, where each derived calculation is
resolved, whether keys are natural or surrogate, where shared dimensions live,
whether the load is full or incremental, and the naming convention.

The method does not replace the official documentation on any of them, and should
not. Capabilities and limits change between releases, and a recommendation based on
what was true six months ago can be wrong today and sound just as confident. What
the method adds is the obligation to raise the decision and back it with
documentation that was read and dated.

The context hook restates this review on every turn of the design phase, so it does
not depend on anyone remembering to open the skill.

### When information is missing to decide

If the design does not have the data it needs to close -- the source is not
understood, a business definition is missing, something has not been measured -- do
not push forward on assumptions. Open a consultation scoped to resolving those
doubts, which produces a document, and pass that document when the real work opens
with `--context`.

The hook injects that path on every turn while the work is open, so the agent reads
it **before** asking. The point is that the information does not get lost between one
conversation and the next. When the real work opens, what the user already answered
does not get asked again.

---

## 13. The platform layer

FAW does not teach how to write an Eventstream or which API deploys a semantic
model, on purpose. That knowledge changes with every release, and maintaining it by
hand guarantees it ages badly without anyone noticing.

Microsoft maintains that layer in
[`skills-for-fabric`](https://github.com/microsoft/skills-for-fabric). The two
layers complement each other because they solve different things. That repository
describes itself as focused on artifact authoring, with no formal gates and no data
contracts, which is what FAW adds.

Rather than naming which skill to read from a list, which goes stale between
releases, the method requires checking what is actually available in the session and
stating which tool is being used or why none applies. That produces a record instead
of an assumption, and it stays true however the vendor reorganizes its catalog. It
is the `tooling` gate, of declaration strength.

Two rules govern the coexistence. FAW governs process and those skills govern
mechanics. If one says "deploy straight to the workspace" and FAW says "through a
pull request", FAW wins, because those skills do not know the project's change
channel. And no write operation they propose is exempt from the approval of the
turn. The skill says how, the user gives the permission.

Detail in [`faw/rules/microsoft-skills.md`](faw/rules/microsoft-skills.md).

---

## 14. The instruments

**Skills** (`skills/`): instructions loaded when a phase or a task starts.
`configure` defines the project profile. `classify`, `profile`, `design` and
`validate` run phases. `backlog` and `roadmap` answer what comes next and where
things are going. `architecture` audits the decisions
that are expensive to reverse. They do not enforce anything by themselves.

**Verifiers** (`scripts/`): each one checks a fact and issues a receipt.

`self_check.py` deserves its own explanation, because it does not verify the
project. It verifies the verifiers. It builds, in a temporary directory, one case
that should pass and one with a known defect that should fail, and confirms each
behaves as expected. Without it, a regular expression changed by accident or an
inverted condition would leave a gate approving everything, and it would look
exactly like a gate that works.

**Hooks** (`faw/hooks/`): state injection on every turn, denial of writes outside the
phase, review of the diff and the pull request body before they exist, and the gate
over writes made through MCP servers.

**The state machine** (`scripts/state.py`): walks the graph, requires the receipts,
and records every transition in `.faw/state.jsonl`, an append-only log. This is not
formal auditing. It is so that the answer to "where were we" does not depend on
anyone's memory two weeks later.

---

## 15. A complete cycle

The commands assume FAW is installed at `<faw>`; when installed as a plugin, any
gate message prints the exact path.

```bash
# CLASSIFICATION: tier and scope get agreed, and only then registered.
# With no external tracker, FAW generates the identifier and creates the ticket file.
python <faw>/scripts/state.py start --tier ARTIFACT --title "fact_movement" \
    --artifact notebook
# Before this, the write hook denies any edit.

# PROFILING: read-only. The receipt goes in docs/faw/<ticket>/profiling.md,
# with every number accompanied by the query that produced it.
python <faw>/scripts/state.py move --to PROFILING \
    --gate user_confirmation="approved tier and scope"

# DESIGN: grain, key, contract and architecture decisions.
python <faw>/scripts/state.py move --to DESIGN \
    --gate profile=docs/faw/T-001/profiling.md
python <faw>/scripts/verify_contract.py contracts/gold.fact_movement.yml --syntax-only

# BUILD: with the official platform tooling checked before writing.
python <faw>/scripts/state.py move --to BUILD \
    --gate user_confirmation="approved design and contract"
# The contract gate is satisfied by the receipt verify_contract.py issued above.
# A --gate declaration cannot satisfy it; machine gates only accept receipts.
# If the ticket covers several tables, declare the scope:
#   --gate tables=gold.fact_movement,gold.dim_account

# VALIDATION: run by the validator agent, which did not build.
python <faw>/scripts/state.py move --to VALIDATION \
    --gate assertions="natural key without duplicates, schema OK, 2705 rows" \
    --gate authorization="explicit approval to write gold.fact_movement" \
    --gate tooling="Spark skill from the official repository"

# PUBLICATION: the hooks check the commit and the pull request before they exist.
python <faw>/scripts/state.py move --to PUBLICATION \
    --gate user_confirmation="approved the validator verdict"
# The schema gate is satisfied by the receipt from the validator run of
# verify_contract.py. A --gate declaration cannot satisfy it.

# CLOSING: requires that no uncommitted changes remain.
python <faw>/scripts/state.py move --to IDLE
```

Pausing and resuming is what makes the method survive closing the session:

```bash
python <faw>/scripts/state.py pause --reason "waiting for the business to confirm"
python <faw>/scripts/state.py resume
python <faw>/scripts/state.py status
```

---

## 16. How to tell it is working

Three signals, from the fastest to the deepest.

**The state line.** If a reply does not start by declaring phase and ticket,
principle 13 is not being followed, and that is the earliest symptom that the others
are not either.

**The per-turn injection.** Checked by passing the context hook a project directory
and seeing whether it returns JSON. If it returns nothing, the project has no `.faw/`
or the hook is failing.

**That the hooks actually block.** The test is attempting the forbidden action and
seeing the denial. Asking for a write with no classified work, or creating a pull
request with a long body.

The failure mode most worth watching. A hook that breaks exits with a non-zero code,
and that is treated as *non-blocking*. A broken hook looks exactly like a hook that
approved the action. That is why hooks get tested by running them rather than by
reading them, and why they all force the encoding of their output. On Windows,
standard output defaults to cp1252, and one character outside that set is enough for
the process to end badly.

---

## 17. What is missing, on purpose

- A promotion criterion between environments. There is none defined, and writing an
  invented one would be worse than the absence.
- Coverage of runs that write from inside a Spark session, where the method detects
  and does not prevent.
- A tier for pipeline orchestration. Dependencies, watermarks and concurrency are
  their own class of failure, and designing it makes more sense after having real
  pipelines under the method.
- Verification of the interaction between row-level security and storage mode,
  which today is a written rule and not a gate.

---

## 18. Installation

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

That registers the hooks, the skills and the validator agent. A project joins by
creating `.faw/` at its root; without that directory every hook exits doing nothing,
so installing the plugin does not impose the method on projects that did not ask for
it.

Then run `/faw:configure` once, so the method stops assuming what it can ask.
Detail in [`docs/INSTALL.md`](docs/INSTALL.md).
