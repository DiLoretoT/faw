# Layout agreement: <TICKET>

> Filled in during DESIGN, after profiling the model and before building a page.
> It is the answer to "what are we going to build", agreed with the user, in the
> same way the brief answered "what is this for".
> `scripts/verify_layout.py` checks it and rejects an unfilled template.

## What the profiling changed

<What measuring the model revealed that the brief did not anticipate. A question
that cannot be answered with the data available, a grain that does not support a
breakdown that was assumed, a measure that already exists and does not need
building. If profiling changed nothing, say so: it is a finding too.>

## Pages

<One block per page. Every page states which question from the brief it answers.
A page that answers no question from the brief either uncovered a question that
belongs in the brief, or does not belong in the report.>

### 1. <page name>

- **Answers:** <the question from the brief, quoted>
- **For:** <who opens this page and what they decide with it>
- **Shows:** <the measures and dimensions, and at what grain>
- **Interaction:** <drill through to where, cross-filtering between what, which
  slicers persist across pages>

### 2. <page name>

- **Answers:** <...>
- **For:** <...>
- **Shows:** <...>
- **Interaction:** <...>

## What is not a page

<Questions from the brief that are answered inside another page rather than
getting their own, and why. This is what keeps a report from growing one page per
question.>

## Navigation

<How someone moves through the report. Where they land, what leads where, and how
they get back. A report of more than two pages that does not say this leaves it to
whatever order the pages happened to be created in.>

## Decisions that will be asked about later

<Visual choices that are not obvious and would be questioned in a review. One
line each. Why a matrix and not a chart, why this measure is on a second axis,
why a page repeats a filter that another one already has.>
