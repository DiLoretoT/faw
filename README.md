# FAW — Fabric Agentic Workflow

A structured way of working with Claude Code on Microsoft Fabric: phases in order,
gates that scripts verify, and hooks that enforce them outside the model.

## What it does

FAW turns a way of working into something the tool enforces, so it does not depend
on remembering it.

Without something like this, how a change gets built depends on the session.
Context falls behind. What you asked for on Monday is not loaded on Wednesday. Some
days you remember to check the source before the table gets written, and some days
you do not. The same task, done twice a week apart, can take two different paths,
and neither one leaves a record.

That variability is the problem. It reduces the surface where an error passes
without anyone reviewing it, which is a smaller claim than "it saves you time" and
one you can actually check.

## Why this is not a set of instructions in a configuration file

Written guidance is a suggestion. The model can follow it, or run out of context,
or decide this case is the exception.

FAW puts the rules where the model cannot skip them. Installed as a Claude Code
plugin, it registers hooks that run before an action and can deny it:

- The first edit with no classified work gets denied, with an explanation of what
  is missing.
- During profiling, which is read-only by definition, writes get denied.
- Every commit gets checked before it exists: protected metadata, invented
  platform literals, content that should not reach a repository someone else reads.
- Writes to the platform through MCP servers go through the phase gates too.

That last one matters more than it sounds. Without it the phases governed the code
and not the data: you could be in profiling and still write to the tenant, because
no file in the repository was touched.

## You approve before it matters

The agent stops three times and waits for you: before profiling the source, before
building anything, and before publishing.

Those are the three moments where the next step is expensive to undo. Approving
there means approving a design choice on purpose, rather than finding out about it
once it is built.

Three and not more, by design. A method that asks for approval at every step
teaches you to say yes without reading.

## It verifies data, not only process

Following the steps is not the point. What the gates check is the artifact:

| Verifier | What it catches |
|---|---|
| `verify_contract.py` | A table published with fewer columns than it declares |
| `verify_model.py` | Reversed relationships, the wrong storage mode |
| `verify_diff.py` | The "formatting only" commit that also drops configuration |
| `verify_platform.py` | A syntax literal invented by analogy |
| `verify_brief.py` | A report built without agreeing on objective and audience |
| `verify_report.py` | The development filter left behind and persisted |
| `self_check.py` | That the verifiers themselves have not broken over time |

A verifier that passes issues a receipt with the hash of what it checked. The state
machine recomputes those hashes, so a receipt issued over an older version of the
file no longer counts.

Gates that are only a statement by the agent are **marked as such**. A gate that
can be lied to without saying so turns the rest into suggestions.

## It uses the vendor's own tooling

FAW does not teach how to write a notebook or which API deploys a semantic model,
on purpose: that changes with every release, and keeping it here guarantees it ages
badly without anyone noticing. Microsoft maintains that layer in
[`skills-for-fabric`](https://github.com/microsoft/skills-for-fabric).

Before building, the method asks which official skills or tools are available in
the session and requires stating which one is being used, or why none applies. It
does not name them from a list, because a list written today sends you to read a
file that will be gone in three months.

Design decisions follow the same rule. The vendor publishes criteria for the
choices that are expensive to reverse, such as which storage mode fits a semantic
model. FAW requires those decisions to be raised and backed by documentation that
was actually read, with the date of the page.

## Start

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

Activate it in a project, which is what makes the hooks act:

```bash
mkdir .faw
```

Then run `/faw-configure` to declare where your tickets live and whether you have a
development environment separate from production. It is optional: without it the
method assumes the strictest case, a single environment treated as production.

## It works without the rest of your tooling

You do not need a ticket tracker. If none is declared, FAW keeps the registry in
the repository and generates the identifiers, with git providing the history. If
you have one with an MCP server connected, it reads and updates it; if you have one
without, it works with the identifier you give it.

You do not need a separate development environment. A single workspace is a
supported pattern, and in that case the method tightens the write rules instead of
assuming there is somewhere cheap to be wrong.

## The limits, without decoration

Code running inside a Spark session and files written from the shell do not pass
through any hook. There the method detects and does not prevent. That is documented
in [`GUIDE.md`](GUIDE.md) rather than promised.

## Documentation

| Document | What it is |
|---|---|
| [`GUIDE.md`](GUIDE.md) | The canonical one: the method, the internals, a full cycle with real commands |
| [`docs/INSTALL.md`](docs/INSTALL.md) | Installation, configuration and how to check it works |
| [`faw/rules/`](faw/rules/) | What the agent reads: principles, phases, surfaces, platform layer |

## Origin

FAW is inspired by **[Dilux Agentic Workflow (DAW)](https://github.com/soydiloreto/dilux-agentic-workflow)**,
a phased workflow with gates for software development pipelines. Four ideas come
from there:

- Phases with gates **enforced outside the model**, so they do not depend on the
  agent remembering them.
- **Tiers**, so a three-line adjustment does not pay the process of a new table.
- The **honest scale of strength** for each gate: saying which ones can be
  satisfied with a statement and which cannot.
- That **whoever validates did not build**.

What changes is the object being verified. DAW checks that the code compiles and
the tests pass; FAW checks that a table has the columns it says it has and that a
semantic model points where it says it points.

There is a fifth thing FAW takes from DAW that is not a feature but a way of
working: **the method gets built iteratively, by using it**. Every rule that exists
arrived because something failed in a specific way and it became clear what would
have caught it.

One difference worth stating: DAW works across several agentic coding tools. FAW
does not. The hooks, the plugin, the skills and the subagent are all Claude Code
mechanisms. What is portable is the method and the Python verifiers; what enforces
the gates is Claude Code.

## This is a work in progress, and feedback is what moves it

FAW is not finished and does not pretend to be. It gains value as it gets used
against real situations: each different project exposes an assumption that was not
universal, a failure no gate was catching, or a rule stricter than the problem
needed. The known limits are written in the [guide](GUIDE.md) so they can be seen
rather than hidden.

**The most useful thing you can contribute is a concrete failure.** You do not have
to propose the fix: the method applies a rule to itself, which is that a rule with
no specific failure mode behind it does not get in. So the valuable half is the one
only somebody who lived it has:

- A wrong number that reached production quietly, and what would have caught it.
- A gate that stopped you for no reason, or let through something it should not.
- An assumption in FAW that does not match how your team works.
- A statement about the platform that is out of date or plain wrong.

Issues and pull requests are welcome. If something in the method was confusing to
read, that is a valid report too.

## License and expectations

[Apache-2.0](LICENSE). Use it, fork it, adapt it to how your team actually works.

This is a way of working that I use, shared as it is. It is not a product and it
carries no warranty, which is what the license says in legal terms and what this
paragraph says in plain ones. Anything an agent does under this method is still
your responsibility to review, the same as anything else you delegate to an AI
tool.
