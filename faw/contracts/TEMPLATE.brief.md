# Report brief: <TICKET>

> Filled in **with the user**, during CLASSIFICATION, before writing a line of the
> report. It is not inferred by reading the semantic model: the model says what
> data exists, not which decision the report has to enable or who takes it.
> `scripts/verify_brief.py` checks it and rejects an unfilled template.

## Objective

<What this report exists for. Which decision it enables, or which question it
closes. If the answer is "to see the data", there is no objective yet: that is an
exploration, and it goes under the EXPLORATION tier.>

## Audience

<Who will open it, in what role, and how often. A concrete role, not "the
business". If it is for internal use by the technical team, say so explicitly: it
changes the level of polish and the client surface rules.>

## Questions it answers

<At least three, each ending in a question mark. They are the acceptance
criterion: if the report does not answer them, it is not ready, however good it
looks.>

1. <...?>
2. <...?>
3. <...?>

## Out of scope

<What is NOT included. This section is what stops the report from growing on its
own, and it is the one most often skipped.>

## Data source

<Semantic model, workspace, connection type and tables consumed. If the report
needs a measure or a column that does not exist yet, that is separate work under
the MODEL or ARTIFACT tier: note it here and classify it separately.>

## Business validation

<Who confirms the numbers are right. A concrete name. If nobody is identified, the
report can be built but **is not published as production** — it is marked as
exploratory and the pending reconciliation is recorded.>
