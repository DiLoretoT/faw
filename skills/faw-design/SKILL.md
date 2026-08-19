---
name: faw-design
description: Runs the DESIGN phase - grain, natural key, data contract, and the architecture decisions that are expensive to reverse. Use before building any artifact or semantic model.
---

# Design

This phase settles what is expensive to change later. A coding mistake is fixed
with a commit; a mistake in grain or storage mode is fixed by rebuilding the
table, the model, and everything downstream of them.

The goal is not to produce a document. It is that every decision the solution will
carry gets made on purpose, with its rationale, and confirmed by the user before
the first line is written.

## What has to be produced

1. **The grain, in one sentence.** "One row per cash movement", or "one row per
   product per day". If the sentence needs a conjunction to be true, the grain is
   not defined.
2. **The natural key, verified against the source.** Verified means the query
   comparing total rows against distinct combinations was actually run. Copying it
   from a specification is not verifying it.
3. **The data contract** (`faw/contracts/TEMPLATE.contract.yml`): columns, types,
   assertions.
4. **The architecture decisions**, below.
5. **The user's confirmation**, which is the gate out of the phase.

## The decisions that get made on their own if nobody looks

Every artifact that gets built leaves architecture decisions settled, whether they
were discussed or not. When they are not discussed, they get made by the default
value of a dialog, by the habit of the previous project, or by the first path that
appeared. They are still decisions; what changes is that nobody can explain why
they were made or what was ruled out.

**What this skill requires is not deciding a fixed list of topics.** It is asking,
before building, which decisions this work will settle, and putting on the table
the ones the user has not discussed. They can then choose to review them or stay
with the default. What must not happen is finding out about the decision once it
is expensive to reverse.

The criterion for which ones to surface: **if changing it three months from now
would mean rebuilding something, raise it now.** If it is reversible with a
commit, it does not need the conversation.

Offer that review even when the user did not ask for it and does not know the
topic, because the consequence of getting it wrong gets paid either way. When they
have no formed opinion, do not choose silently for them and do not deliver a
lecture. Explain in two or three sentences what each option implies **for this
specific case**, recommend one with its rationale, and move on.

### Where they tend to hide

This is not a list to walk through on every piece of work. It is where to look to
spot which ones apply to the artifact about to be built.

- **Storage mode of the semantic model.** The most expensive to reverse when a
  model is involved. It depends on volume, on how often the data changes, and on
  the latency whoever consumes the report will tolerate. It also has interactions
  worth checking before rather than after: Direct Lake does not support calculated
  columns, and row-level security on the source tables can change the behavior of
  the chosen mode or make the query fail.
- **Grain** of each fact table, and whether more than one is needed.
- **Where each derived calculation is resolved**: materialized upstream, or
  expressed as a measure. Principle 5 covers the criterion and its exceptions.
- **Surrogate or natural keys**, and what happens to rows whose key does not
  resolve.
- **Where shared dimensions live** when more than one model consumes them.
- **Load strategy**: full or incremental. If incremental, what the watermark is
  and what happens when a run fails halfway.
- **Naming convention**, cheap to settle at the start and impossible to change
  later.

### How a recommendation is backed

Every definitive statement about the platform -- "X cannot be done", "A is better
than B", a limit of a feature -- is backed by official documentation that was
read, citing the date of the page. Capabilities change between releases, so a
recommendation based on what was true six months ago can be wrong today and sound
just as confident.

If the documentation does not say it explicitly, declare it as your own inference.
That distinction is the difference between a design that is grounded and one that
looks grounded.

## When the design is not ready to be settled

Sometimes the request arrives without the information needed to close the design:
the source is not understood, a business definition is missing, or a platform
decision depends on data nobody has measured.

In that case **do not push forward on assumptions**. Offer the user a prior
consultation. A `QUESTION` tier piece of work scoped to resolving exactly those
doubts, which reads whatever documentation is needed, measures the source, and
returns a document with the answers.

That document is then passed as context when the real work opens:

```bash
python <faw>/scripts/state.py start --tier ARTIFACT --title "..." \
    --context docs/faw/consultations/<id>.md
```

The point of doing it this way is that the information does not get lost between
one conversation and the next. When the real work opens, **do not ask again what
the user already answered**. Restate in one line what was decided, and ask only
for what is new.

## Before building

The phase closes with the user's confirmation, and the closing question says what
will be done if they confirm, not only which phase comes next (principle 14).

Check which official platform skills are available in the session and state which
one applies to this artifact, or why none does. Read it **before** building, not
while building. See [`microsoft-skills.md`](../../faw/rules/microsoft-skills.md).
