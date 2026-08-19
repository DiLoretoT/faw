---
name: faw-architecture
description: Architecture review of what is being built, contrasting the decisions taken against official documentation, forums and community articles. Use when closing a stage, before replicating a pattern to another domain, or when a decision starts to hurt.
---

# Architecture review

Contrasts what is being built against what the platform actually supports and what
the rest of the field does. **This is not a code review**: it does not look at
whether the code is well written, it looks at whether the decisions are the right
ones.

## When it applies

- When closing a stage, before the decision becomes expensive to change.
- **Before replicating a pattern to another domain.** This is the point of highest
  leverage: a decision copied four times becomes irreversible.
- When a decision starts to hurt and it is not clear whether the problem is the
  decision or the implementation.
- When the vendor changes something relevant.

## The rigor rule, non-negotiable

Every definitive statement about the platform -- "X cannot be done", "A is better
than B", the limits of a feature -- is backed by **official documentation that was
read**, citing the date of the page.

- A search engine summary tells you **where to look**, never what to cite.
- If the documentation does not say it explicitly, declare it as **your own
  inference or observation**, not as documented behavior.
- Never say "here is the link that confirms it" without having read that specific
  link and checked that it says that.

Platform products change often. Nothing known three months ago is settled.

## What to do

### 1. Inventory the decisions in force

From architecture documents, contracts and artifact headers. Each one with:

- What was decided.
- When, and with what information.
- What depends on it today, which is what defines how much changing it costs.

Prioritize the ones that are **hardest to reverse**: naming, fact grain, where
conformed dimensions live, storage mode of the semantic model, write policy. A
column name gets changed; the grain of a fact does not.

### 2. Contrast against the official source

For every relevant decision, find and **read**:

- The documentation page that covers it. Record the URL and its date.
- Whether there are guardrails or capacity limits that apply.
- Whether the feature is in preview, generally available, or deprecated.

Use whichever documentation search tools are available in the session; failing
that, fetch the official documentation site directly. Vendor repositories for
official examples.

### 3. Contrast against the community, as a counterweight and not as a foundation

Look specifically for what the official documentation will **not** tell you:

- Known bugs and current workarounds.
- When the official recommendation does not work in practice.
- What people with the same problem chose, and what happened to them afterwards.

**Mark every community source as such.** It is evidence that something works or
fails in the field, not evidence of how the platform behaves.

### 4. Issue a verdict per decision

| Verdict | What it means |
|---|---|
| **Confirmed** | Aligned with the official documentation. With the citation. |
| **Confirmed with caveats** | Correct, but there is a limit or condition that was not being considered. |
| **Debatable** | Defensible, but there is a better-supported alternative. With the trade-off stated. |
| **To revisit** | It rests on something that changed, or that was never verified. |
| **No verifiable backing** | There is no documentation for or against it. Declared as your own judgment. |

For anything that is not "Confirmed": **what changing it would cost today**, and
**what it will cost in three months**. That comparison is what decides.

### 5. Look for what was never decided

Sometimes the most important finding is a gap: something nobody decided that is
resolved by a default. A default nobody chose is a decision the tool made for you.

## What to produce

`docs/faw/architecture/<date>-review.md`:

```markdown
# Architecture review: <date>
Scope: <what was reviewed>

## Verdicts
| Decision | Verdict | Basis | Cost of changing |
|---|---|---|---|

## Findings that require action
1. **<title>** - what, why, proposal, cost.

## Gaps: what nobody decided
- ...

## Official sources
| Page | URL | Date | What it supports here |

## Community sources (counterweight, not foundation)
| Source | Author / date | What it supports |

## No verifiable backing
- <statements that stand as your own judgment, declared as such>
```

If the review changes a decision, **update the project architecture document**: the
verdict is useless if the next session reads the old decision.

## Traps

- **Citing a search engine summary as if it were the documentation.** It is the
  most common failure and the most damaging: the design gets built on something
  false.
- **Reviewing only what hurts.** The decisions that are not bothering anyone also
  age; naming and grain make the least noise and cost the most to change.
- **Confusing "the community does it this way" with "it is correct".** And the
  inverse too: the official documentation recommends the general case, not
  necessarily yours.
- **Finishing without a verdict.** A review that says "there are options" is
  useless. Every decision comes out with a verdict and, where it applies, a
  proposal.
