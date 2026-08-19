---
name: faw-roadmap
description: Contrasts what was planned against what actually exists on the platform, and when there is no defined direction, helps build one using the official adoption framework as a reference. Use when reviewing progress, replanning, or when the backlog has run out of things to propose.
---

# Roadmap

This skill does two different jobs depending on what the project already has.

If there is a plan, it contrasts it against reality and shows the differences. If
there is none, it helps build one. The second situation is more common than it
looks. A project can have a backlog full of tasks and still have no direction,
because a backlog says what is pending and a roadmap says where things are going.

---

## When there is a plan: contrast three states

Three things that start out identical and diverge over time:

1. **What was planned**: what the backlog or the direction document says.
2. **What is recorded**: what the team believes is done.
3. **What exists**: what is actually deployed on the platform.

The material of this skill is the differences. They are not hidden or softened. A
discrepancy is information about why the plan and reality separated.

| Deviation | What it means |
|---|---|
| Done but not closed | The work exists and the record does not show it |
| Closed but not done | The record says finished and it is not on the platform, or only partly |
| Done without planning | Work appeared that nobody planned: usually urgencies or discoveries |
| Planned long ago, never started | A candidate for not being needed any more |
| Blocked with no owner | Nobody holds the action that unblocks it |
| Built twice | Two artifacts solve the same thing without knowing about each other |

For each deviation, state **the cause**, not only the fact. Information that
arrived late, technical reality different from what was expected, a wrong
estimate, or something discovered while building. Without the cause the list is an
inventory; with it, it supports a decision.

Verify against the platform, not against the repository. The repository declares
the intent and the deployed environment is what exists (principle 11).

The output is not a progress report. The question it answers is whether the plan is
still the right one.

---

## When there is no plan: build the direction

If the project has no roadmap, this skill offers to build one instead of treating
the topic as closed. Having one is not mandatory. A small project can work fine
resolving requests as they arrive. But it should be a decision rather than an
oversight, because without direction the data platform grows by accumulation and
each piece answers the urgency of its moment.

### The reference: the official adoption roadmap

Microsoft publishes the **Microsoft Fabric adoption roadmap**, which organizes
adoption into twelve areas and defines maturity levels for locating yourself in
each one. The areas are: data culture, executive sponsorship, business alignment,
content ownership and management, content delivery scope, center of excellence,
governance, mentoring and user enablement, community of practice, user support,
system oversight, and change management.

*Checked on Microsoft Learn, page dated 2024-12-30. There is also an earlier "Power
BI adoption framework" aimed at partners; the documentation itself indicates the
adoption roadmap is the current guidance. When citing this, read the page and use
its date.*

**How it is used here, and how it is not.** That framework is organizational. It
covers culture, sponsorship and governance, which are decided outside any
technical tool. FAW does not govern any of that and should not pretend to. What
this skill does is use it as a **direction checklist**, so a technical roadmap is
not built by looking only at the pile of pending tasks.

Of the twelve areas, four translate into concrete data engineering work:

| Area | What it opens up for the technical roadmap |
|---|---|
| **Content ownership and management** | Who owns each artifact? What happens when whoever built it is gone? |
| **Governance** | Is there a convention for names, layers and permissions, or does each piece follow its own? Is sensitive data identified? |
| **System oversight** | Is anyone watching capacity consumption, failed runs, models that stop refreshing? |
| **Content delivery scope** | Is this used by one person, one team, or the whole organization? It changes what has to be built |

The other eight get mentioned if the user wants to locate themselves in the full
framework, but they do not become tickets. They are not engineering work.

### What gets produced

A short direction proposal with three to five objectives, saying for each one what
problem it solves, what would have to be built, and what blocks it today. It is
ordered by technical dependency, like the backlog.

The roadmap is stored in the repository at `docs/faw/roadmap.md`, and reviewed when
something relevant changes rather than on a fixed cadence.

**Tickets are not created from the roadmap without the user's approval.** An
approved roadmap is not permission to fill the backlog. It is the frame from which
tickets get proposed one at a time.
