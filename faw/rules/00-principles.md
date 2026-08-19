# Principles: they apply in every phase

These fourteen rules do not depend on the tier or the phase. If one of them
conflicts with a specific instruction, the rule wins and the conflict is stated.

## Where they live and what enforces them

This file is the source. The agent reads it when opening a piece of work, and the
context hook restates the principles that govern the current phase on every turn,
so it does not depend on having read this once at the start.

That is not enough on its own, and it is worth being precise about why. A
principle can be backed in three different ways, and the difference determines
what happens when someone does not follow it:

| Backing | What it means | What happens if it is not followed |
|---|---|---|
| **Gate** | A verifier checks it and issues a receipt the state machine recomputes | The phase does not advance |
| **Hook** | A program intercepts the action before it happens | The action is denied |
| **Reading** | It is written here and the agent applies it | Nothing stops it; it is detected later, or not at all |

Every principle states which one it has. The ones marked **reading** depend on
the agent's judgment. That is not a defect to hide, it is the real limit of the
method. A principle marked as reading and presented as a guarantee would be a
gate that does not exist, which is the exact failure FAW is built to prevent.

---

## 1. Evidence before assertion

*Backing: reading, plus the profiling receipt in the tiers that require it.*

Every number that appears when a phase closes comes from a query that can be
shown.

- If it was measured, give the number and the query.
- If it was estimated, say **"estimated"** and where it comes from.
- If it was not measured, say **"not measured"**. There is no third option.

A number without a source is not data, it is an opinion in the shape of data. In
data work, the number *is* the deliverable.

## 2. Validate the schema, not just the count

*Backing: the `contract` and `schema` gates, checked by `verify_contract.py`.*

A table is never considered validated on a row count. The name and type of every
column are compared against its contract.

The failure this closes: a table can match the expected number of rows exactly
and have half the columns it declares. Whoever looks only at the count passes it,
and the count was correct.

When any write closes, report rows **and** columns.

## 3. Explicit authorization per turn to write to the platform

*Backing: a hook, over the writes that go through MCP tools. In a project with no
separate development environment, the authorization also has to be written down
before it runs.*

No write to the platform without explicit approval **in the same turn**. This
includes temporary tables and writes made "just to check something". No exception
by size or by intent.

Before asking, state precisely: which table, which operation, how many rows are
affected, what gets created and what gets deleted. Afterwards, report what
actually happened.

The limit of the backing: the hook reaches MCP tools, not the code that runs
inside a Spark session. There the principle is reading again.

## 4. Silence is the enemy

*Backing: reading, with the schema part backed by the `contract` gate.*

Between an artifact that fails and one that returns a doubtful number, always the
one that fails.

- No foreign key is left null: it goes to a **visible** Unknown member.
- Every table carries a natural key assertion that stops execution on duplicates.
- An unintended schema change makes the write fail instead of overwriting.
- Values that fit no category get their own category; they are not folded into
  the last one.

## 5. Resolve derived values as far upstream as the design allows

*Backing: reading. This is a design criterion, not a mechanical rule.*

The default is to materialize a derived column upstream rather than in the
consumption layer. The reason is cost and consistency: what is computed once on
write is computed once, and every consumer sees the same value, while what is
computed in the model is recomputed per query and can differ between two reports
that define the same thing twice.

**Where the default does not apply**, and these are legitimate cases rather than
exceptions to justify:

- A calculation that depends on the user's filter context **has to** be a
  measure. A ratio, a weighted average or a running total cannot be materialized
  as a column without fixing the aggregation level in advance.
- A column whose cardinality would grow the table disproportionately may belong
  in the model even though it is computable upstream.
- A calculation that changes often and does not justify reprocessing the whole
  table each time.

One platform fact is fixed and worth keeping in mind while deciding: **Direct
Lake does not support calculated columns**. In a Direct Lake model, resolving
something as a column in the model is not an option at all, so the decision is
between materializing upstream and expressing it as a measure.

The operative rule is that where a calculation lives gets decided and explained
during design, not that there is a single correct place for it.

## 6. Statements about the platform need documentation that was read

*Backing: the `platform` gate for syntax literals, checked by
`verify_platform.py`. For everything else, reading.*

Every definitive statement about the platform -- "X cannot be done", "A is better
than B", the limits of a feature -- is backed by official documentation that was
**read**, citing the date of the page.

A search engine summary tells you where to look, not what to cite. If the
documentation does not say it explicitly, it is declared as **an inference or an
observation of your own**, never as documented behavior.

## 7. Know who reads each surface

*Backing: hooks, over the diff of every commit and the body of every pull request.*

Before writing anywhere, ask who reads it. Detail in
[`client-surface.md`](client-surface.md).

In short: a remote repository is **not** an internal workspace. FAW treats every
governed repository as client surface, without distinguishing whose it is.

## 8. Do not fight the serializer

*Backing: reading.*

When the platform reserializes an artifact into its canonical format, accept that
format. If a diff appears that is only formatting, commit it and close the cycle.
Never revert it in a pull request.

Before approving a diff as cosmetic, inspect it **whole**, including the header.
A summary of added and removed lines is not proof.

## 9. Reproducing code by hand is dangerous

*Backing: reading.*

Running a notebook by reproducing it in an interactive session is sometimes the
only option. When it happens:

- reproduce it **completely**, never an abbreviated version;
- print the schema of the result at the end and compare it against the source
  file;
- state in the closing report that this was a manual reproduction and not a run
  of the real artifact.

The characteristic failure is writing a trimmed version, forgetting that it was
trimmed, and validating it as if it were the real one.

## 10. A job reporting success is not evidence

*Backing: reading.*

A pipeline or notebook with a "Succeeded" status does not prove that anything
happened. A copy activity against an empty source, a merge that matched no rows,
a notebook whose guard assertion never fired because the input frame arrived
empty: all of them finish successfully.

- Never read a job status as evidence that the work was done.
- Compare the real delta -- rows written, rows affected -- against an expected
  minimum.
- "Succeeded" and "0 rows affected" at the same time is a failure, not a quiet
  success.

## 11. Verify against the real environment, not against the code

*Backing: the `metadata` gate over the diff. For every other surface, reading.*

The repository declares the intent; the deployed environment is the source of
verification. Do not assume they match without checking.

This generalizes what the `metadata` gate applies to a diff: a change that looks
harmless can alter configuration nobody is looking at. The same pattern shows up
elsewhere:

- A variable library with different values per environment that the notebook
  assumes are the same.
- Workspace permissions changed by hand in the interface, without passing through
  the repository.
- A storage shortcut pointing somewhere other than where the code believes.

Before accepting a reading of the environment made from memory or from the code,
confirm it against the real workspace.

## 12. A relationship that publishes without error is not verified

*Backing: the `model` gate for direction and declared properties, checked by
`verify_model.py`. Proving it with real data is reading.*

That a semantic model publishes and its queries run does not prove a relationship
between a fact and a dimension points in the right direction. When the modeling
closes, confirm relationship by relationship that the fact stays on the "many"
side, by testing a real filter from the dimension against the expected count, not
by checking that the editor shows no error.

## 13. The phase is declared in every reply

*Backing: the context hook injects the reminder every turn; whether the line
appears is reading.*

Every reply starts with a state line. With work open: `{TIER} - {action} |
{ticket}: {title}`. For a standalone question that touches nothing: `[question]`.

This is not decoration. It is the only way for the user to notice a deviation
**as it happens**, without having to ask. Without the state line, skipping the
classification is invisible until the work is already done; with it, a tier
declared in a phase that was never opened stands out in the second message.

It is the cheapest rule in the method and the one that exposes fastest that the
others are not being followed.

## 14. No closing question without saying what comes next

*Backing: reading.*

Every checkpoint question ("shall I close here?", "shall we start?") is preceded
by **one concrete sentence about what happens next** if the user says yes. Naming
the next phase is not enough: that says *where*, not *what*.

Wrong: *"Shall I close this and move to profiling?"*
Right: *"I am going to profile the source: run a total row count against a count
of distinct keys, and measure nulls per column. Shall I go ahead?"*

Without the action sentence, the user approves a phase in the abstract and finds
out what the agent did once it is done. With it, the approval is about something
concrete and the deviation shows up before it happens.

Any skill that closes with a question puts that sentence first. If the real
answer depends on what gets found, say so: do not invent a generic sentence to
satisfy the form.
