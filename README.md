# FAW — Fabric Agentic Workflow

A way of working with Claude Code on Microsoft Fabric that the tool enforces, so it
does not depend on remembering it. Phases in order, gates that scripts verify, hooks
that run outside the model, and three points where you approve before anything
expensive happens.

Without something like this, how a change gets built depends on the session.
Context falls behind. What you asked for on Monday is not loaded on Wednesday. Some
days you remember to check the source before the table gets written, and some days
you do not. The same task, done twice a week apart, takes two different paths, and
neither leaves a record.

FAW does not promise to save you time. It reduces the surface where an error passes
without anyone reviewing it, which is smaller and checkable.

## Install

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

Activate it in a project, which is what makes the hooks act:

```bash
mkdir .faw
```

Then run `/faw-configure` once, so the method stops assuming what it can ask.
Full steps in [`docs/INSTALL.md`](docs/INSTALL.md).

## What it does

Written guidance is a suggestion. The model can follow it, run out of context, or
decide this case is the exception. FAW puts the rules where it cannot skip them:
the first edit with no classified work is denied, writes during profiling are
denied, every commit is checked before it exists, and writes to the platform
through MCP servers go through the phase gates too.

That last one matters more than it sounds. Without it the phases governed the code
and not the data: you could be in profiling, which is read-only by definition, and
still write to the tenant, because no file in the repository was touched.

**You approve at three points**: before profiling the source, before building, and
before publishing. Those are the moments where the next step is expensive to undo.
Three and not more, by design. A method that asks at every step teaches you to say
yes without reading.

**The gates verify the artifact, not the process.** That a table has the columns it
declares, that a relationship points where it says, that a commit described as
formatting does not also drop configuration. A verifier that passes issues a
receipt with the hash of what it checked, and a receipt over an older version of
the file no longer counts. Gates that are only a statement by the agent are marked
as such: one that can be lied to without saying so turns the rest into suggestions.

The method, the phases and what each gate catches are in [`GUIDE.md`](GUIDE.md).

## It works without the rest of your tooling

You do not need a ticket tracker. If none is declared, FAW keeps the registry in
the repository and generates the identifiers, with git providing the history. If
you have one with an MCP server connected, it reads and updates it; if you have one
without, it works with the identifier you give it.

You do not need a separate development environment either. A single workspace is a
supported pattern, and there the method tightens the write rules instead of
assuming there is somewhere cheap to be wrong.

## The limits

Code running inside a Spark session and files written from the shell do not pass
through any hook. There the method detects and does not prevent. That, and what
else is missing on purpose, is written down in [`GUIDE.md`](GUIDE.md) rather than
promised.

## Docs

| Document | What it is |
|---|---|
| [`GUIDE.md`](GUIDE.md) | The canonical one: the method, the internals, a full cycle with real commands |
| [`docs/INSTALL.md`](docs/INSTALL.md) | Installation, configuration, single-use overrides, how to check it works |
| [`faw/rules/00-principles.md`](faw/rules/00-principles.md) | The fourteen principles, each stating what enforces it |
| [`faw/rules/phases.md`](faw/rules/phases.md) | What each phase does, produces, and needs to close |
| [`faw/rules/client-surface.md`](faw/rules/client-surface.md) | Who reads what you write, and what never goes there |
| [`faw/rules/microsoft-skills.md`](faw/rules/microsoft-skills.md) | How this coexists with the vendor's own skills |

## Where it comes from

FAW is inspired by [DAW — Dilux Agentic Workflow](https://github.com/soydiloreto/dilux-agentic-workflow),
a phased pipeline with gates for software development. Four ideas come from there:
gates enforced outside the model, tiers so a small change does not pay a large
process, an honest scale of how strong each gate is, and that whoever validates did
not build.

What changes is the object. DAW checks that the code compiles and the tests pass;
FAW checks that a table has the columns it says it has. There is a fifth thing it
takes that is not a feature but a way of working: the method gets built
iteratively, by using it. Every rule that exists arrived because something failed
in a specific way.

One difference worth stating: DAW works across several agentic coding tools. FAW
does not. The hooks, the plugin, the skills and the subagent are Claude Code
mechanisms. The method and the Python verifiers are portable; what enforces the
gates is not.

## This is in progress, and feedback is what moves it

FAW is not finished and does not pretend to be. Each different project exposes an
assumption that was not universal or a failure no gate was catching.

**The most useful thing you can contribute is a concrete failure.** You do not have
to propose the fix: the method applies a rule to itself, which is that a rule with
no specific failure mode behind it does not get in. So the valuable half is the one
only somebody who lived it has — a wrong number that reached production quietly, a
gate that stopped you for no reason, an assumption that does not match how your
team works, a statement about the platform that is out of date.

Issues and pull requests are welcome. If something was confusing to read, that is a
valid report too.

## License

[Apache-2.0](LICENSE). Use it, fork it, adapt it to how your team actually works.

This is a way of working that I use, shared as it is. It is not a product and it
carries no warranty, which is what the license says in legal terms and this says in
plain ones. Anything an agent does under this method is still yours to review, like
anything else you delegate to an AI tool.
