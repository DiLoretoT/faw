---
name: report-design
description: Runs PROFILING and DESIGN for the REPORT tier. Explores the data, reads it through the business, and turns that into a layout agreement of pages and questions before any page gets built. Covers both a new report and a change to one that already exists. Use after the brief is agreed and before building a report.
---

# Report design

Between the brief and the first page there are two phases, and they exist because
a report built without them is precise about questions nobody asked.

The brief already settled what the report is for, who opens it and which
questions it has to answer. What is still missing is whether the data can answer
them, and what shape the answer takes.

## The three hats, in order, on the same context

This is one process in three passes, not three separate reviews. Each pass reads
what the previous one found and builds on it. Restarting from scratch on each
one loses what was learned and asks the user again for what they already said.

**Do not delegate these passes to separate agents.** The value is in the
accumulation, and a subagent starts without the context that makes the next pass
worth anything. The one delegation FAW does make is validation, precisely because
there breaking the context is the point.

### First pass: what is actually in the data

This is PROFILING, and it is read-only.

Measure the model the report is going to consume:

- Tables and their grain. What one row means in each.
- Row counts, and the business totals the report will have to reproduce.
- Measures that already exist. A report that needs a measure nobody wrote is a
  MODEL tier ticket, not something to solve inside a visual.
- Cardinality of every dimension used for slicing. A slicer over a
  high-cardinality column is a decision, not a default.
- Data quality where it affects an answer: nulls in a column the report groups
  by, sentinel dates, categories that swallow everything else.
- The date range with data, against the range the report claims to cover.

Every number comes with the query that produced it (principle 1).

**When the model cannot be queried from here.** A working folder without an MCP
server or a connection cannot run the measurements. Say so rather than
estimating: write the queries, hand them to the user, and record the results they
return. What could not be measured is declared as not measured. A profiling
receipt of invented numbers passes the gate and poisons everything downstream.

Produced: `docs/faw/<ticket>/profiling.md`.

### Second pass: what those data mean to the business

Now read the same findings through whoever is going to use them.

- What does the audience in the brief decide with this, and how often?
- What does a number being high or low mean *in this domain*? A ratio that is
  healthy in one vertical is an alarm in another.
- What comparison makes a number meaningful? Against the previous period, against
  a target, against a peer group. A figure without a reference is trivia.
- What does this audience already look at today, and what would they have to stop
  doing if this report works?
- Which of the brief questions turned out to be harder than it looked once the
  data were measured, and which turned out to be trivial?

This pass produces no document of its own. It changes what the third pass builds,
and what changed goes into the layout agreement.

### Third pass: what gets built

Now the layout, with everything above already known.

For each question in the brief, decide how it gets answered: which measures,
which dimensions, at what grain, in what visual, and whether it earns its own
page or is read alongside another question.

The output is `docs/faw/reports/<report>/layout.md`, from
`faw/contracts/TEMPLATE.layout.md`. `scripts/verify_layout.py --report "<report>"`
checks it, and what it requires is that **every page states which question from
the brief it answers**. A page that answers none either uncovered a question that
belongs in the brief, or does not belong in the report.

## Changing a report that already exists

The layout lives under the report and describes all of it, so a change amends the
document that is there rather than opening a rival one. Three passes still run,
and what changes is where each one starts.

**First pass.** Only the data the change touches. What was already profiled for
this report was profiled against a state of the model that may have moved, so
re-measure what the change reads instead of trusting the earlier numbers, and
leave the rest alone.

**Second pass.** Why the report is being changed, which is a business question
and rarely the one that gets asked. "Add revenue by region" is a request, not a
reason. What decision is not being made today with what is on screen? Often the
answer is that an existing page is not read, and adding a page makes that worse.

**Third pass.** Amend the layout. New pages are added with the question each one
answers, like any other. Pages that change what they answer are rewritten.
**Pages that stop being useful are removed from the report and from the
agreement**, and this is where a change either keeps a report readable or grows
it one page at a time until nobody opens it. Removal is proposed to the user with
the reason, never done silently.

Amending changes the file's hash, so the receipt from the previous version stops
being valid and the gate is crossed again on the amended text. That is the
intended behaviour: the agreement being checked is the one in force, not the one
that was agreed a year ago.

**When the report has no layout.** Nobody wrote one, which is the usual state of
an inherited dashboard. Reconstruct it from what is built: one entry per page
with what it shows and, where it can be established, what question it answers.
The pages whose purpose nobody can state are the finding, and they go to the user
as a question rather than being written up as if they had been agreed.

## What a good report does with the tool

Aim high on what the platform makes possible, and check the official skills for
the mechanics rather than working from memory.

**Interaction is the point, not decoration.** Drill through so a number leads to
the rows behind it. Cross-filtering so selecting somewhere explains what happens
elsewhere. Slicers that persist where following the thread across pages makes
sense, and reset where it does not. A report where nothing can be clicked is a
printed sheet on a screen.

**Simplicity is a result, not a starting point.** One page that answers one
question well beats a page with six visuals that answers none. What is not read
gets removed.

**Data before aesthetics, and then the best aesthetics that leaves room for.**
Ordering, alignment, consistent formatting and a scale that does not lie are part
of reading a number correctly. Everything after that is decoration, and
decoration never wins against legibility.

**What the number is compared against belongs on screen.** A total with no
reference forces the reader to supply one from memory, and memory invents.

## Closing

The phase closes with the user confirming the layout agreement. That is the
second of the three checkpoints in this tier, and what gets agreed there is the
extent of the report: how many pages, what each one answers, and what was left
out.

The closing question says what will be built if they confirm, not just which
phase comes next (principle 14).

If building shows the agreed layout is not viable, the work goes back to DESIGN
and the agreement changes. It does not drift in silence: `verify_report.py
--layout` compares the pages that were built against the ones that were agreed,
and a report that no longer matches its agreement does not publish.
