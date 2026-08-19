# Client surface

Before writing anywhere: who reads this?

FAW does not distinguish own repositories from client repositories. Every
governed repository is treated as **client surface**: whatever is written there is
read by the recipient of the repository, whether that is a client, another team,
or any third party. The distinction is deliberately absent: it is a decision made
once, which removes the chance of getting it wrong repository by repository.

## The map

| Surface | Who reads it | What can go there |
|---|---|---|
| Chat with the user | Only the user | Everything |
| `docs/faw/` in the working repository | Whoever reads the repository | Method artifacts (the gate does not inspect them); if the reader should not see them, point them elsewhere with `artifacts_in` |
| Internal project tracker | The internal team | Everything: findings, questions, reasoning |
| **The working repository** | **The recipient of the repository** | Only what changed and how it was validated |
| Pull requests, commits, issues | **The recipient** | The same |
| The platform workspace | **Whoever uses the tenant** | Artifact names and descriptions |
| Documents and presentations | **The client** | The deliverable, without internal methodology |

**The case that gets confused every time:** a remote repository feels like an
internal workspace and is not. Every commit, pull request and issue is read by
whoever has access, and in consulting work that is the client, in their own house.

## What never goes to a client surface

- **Referring to the client in the third person.** Writing "topics to raise with
  the client" inside the client's own repository.
- **Assigning tasks to the client's people.** "Confirm with finance", "ask
  so-and-so". That belongs in the internal tracker, and the user raises it when
  it makes sense.
- **Open findings and business questions.** They create questions and noise
  somewhere nobody can answer or contextualize them.
- **Discarded alternatives and long design reasoning.** One line of rationale per
  decision is enough.
- **Internal methodology.** Reuse of in-house templates or frameworks, names of
  other clients or projects, references to internal repositories.
- **AI attribution.** Not in commits, not in pull request bodies, not in comments.

## What does go in a pull request

1. What changed: a table of new columns, artifacts touched.
2. One line of rationale per non-obvious decision.
3. The validation numbers.
4. A deployment note, if the change needs a manual step.

Nothing else. If the body runs past one screen, something in it does not belong.

## Where everything else goes

| Content | Destination |
|---|---|
| Data findings, questions for the business | The project's internal tracker |
| Complete design reasoning, alternatives | `docs/faw/<ticket>/design.md`, which the gate exempts, or outside the repository via `artifacts_in` if the reader should not see it |
| Data contracts, profiling receipts | The same. Path in `.faw/config.json` under `artifacts_in` |
| Durable architecture decisions | The project's internal technical documentation |
| Learnings that carry to other projects | A knowledge base |

> This applies to **the files in the repository, not only to the pull request**.
> A notebook, the markdown of a cell, a print statement that runs on every
> execution, the text of a report visual: the recipient reads all of it the same
> way they read a pull request. The `surface` gate checks it over the diff before
> every commit, with `docs/faw/` and `.faw/` as the only exempt paths.

## What each project declares

The generic patterns live in the code. What is specific to each project is
declared in `.faw/config.json`, which is not versioned, in two lists that are
empty by default:

- `client_people`: names of people that must not appear in files or pull requests.
- `internal_literals`: names of other clients, repositories or in-house
  methodology that must not leak.

## The check, before publishing

Before creating a pull request or committing, reread the text looking for:

- [ ] The word "client" referring to whoever is going to read it.
- [ ] Names of the client's people with a task assigned to them.
- [ ] Sections of findings, pending items or open questions.
- [ ] Names of other clients or of internal repositories.
- [ ] Any mention of AI assistance.
- [ ] More than one screen of text.

If any of them shows up, fix it before publishing, not after.
