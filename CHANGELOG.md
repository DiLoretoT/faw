# Changelog

## 4.1.0 - 2026-08-22

### Added

- The REPORT tier gains profiling and design. A report used to go straight from
  the brief into building, so it was built on data nobody had measured and pages
  nobody had agreed. It now profiles the semantic model it will consume and
  agrees a layout first.
- The `layout` gate, checked by `verify_layout.py`. What it verifies is the
  layout **agreement** and not the layout: that every page states which question
  from the brief it answers, and that no template placeholder survived. Whether
  the layout is any good is not machine-verifiable and the gate does not claim
  it is.
- `verify_report.py --layout` cross-checks the pages that were built against the
  ones that were agreed. Without it the agreement was read once on the way into
  building and never again, so a report could drift from it and still publish.
- Back edges `BUILD->DESIGN` and `DESIGN->PROFILING` for REPORT. A layout that
  building shows to be unviable previously had only two exits: abandoning, or
  drifting from the agreement in silence.
- `report-design` skill, covering the three passes that make up profiling and
  design for a report: what is in the data, what those data mean to the business,
  and what gets built. The passes accumulate in one context on purpose, because
  restarting each one loses what the previous found.
- `TEMPLATE.layout.md`, and self-check cases for both new checks.

### Changed

- The three checkpoints are no longer described as fixed phases. Which ones they
  are depends on the tier: for REPORT they are the end of classification, design
  and build. Three remains the ceiling.
- The per-turn context takes the tier into account, not only the phase. A report
  in DESIGN was being told "grain in one sentence, natural key verified", which
  is table guidance, and what arrives every turn outweighs what is read once.
## 4.0.3 - 2026-08-22

### Fixed

- Any ticket that did not declare its tables on the move raised a `NameError`
  instead of checking the `contract` and `schema` gates. Moving receipts into the
  governed folder in 4.0.2 turned a module constant into a function and left
  three references to the old name in the helper that lists issued receipts.
  That helper is what resolves the scope when the move carries no
  `--gate tables=`, which is the single-table case and the common one.

### Added

- A self-check case for the undeclared-scope branch, verified in both
  directions. The existing multi-table case always declares `tables=`, so it
  exercised the other branch and stayed green while this one was broken.

## 4.0.2 - 2026-08-20

### Fixed

- A receipt outlived the ticket that produced it and satisfied the gate of the
  next one. Receipts recorded what was checked and over which files, but not for
  which ticket, and the machine gates never asked. With the input file still on
  disk and its hash still matching, a closed ticket's brief let the following
  ticket enter BUILD having produced no brief of its own. Reproduced before
  fixing. Receipts now record their ticket and are rejected for a different one.
- Verifiers resolved their paths against the current directory rather than the
  governed folder, so one run from a subdirectory wrote its receipt into a
  `.faw` the state machine never reads. The fix in 4.0.1 reached the state
  machine and the hooks but not the verifiers.

### Added

- A self-check case covering receipt scope, verified in both directions: it
  fails against the code that had the defect and passes against the fix.

## 4.0.1 - 2026-08-20

### Fixed

- The validator agent shipped with `tools: All tools` in its frontmatter. That
  field takes a list, so Claude Code split the prose into `All` and `tools`,
  resolved neither to a real tool, and refused to launch the agent. The
  VALIDATION phase was unreachable through its own agent from 3.0.0 until now.
  The line is gone: with no `tools` field the agent inherits every tool, and
  `disallowedTools: Edit, NotebookEdit` still keeps it from editing what it
  judges, which is the guard that matters. Reported as issue #2.

### Added

- A self-check case that parses the frontmatter of every distributed agent and
  fails when a tool field holds something that is not a tool name. A broken
  frontmatter used to surface only at the moment of launching the agent, with
  nothing else detecting it.

## 4.0.0 - 2026-08-19

The working folder becomes the primary model. FAW no longer assumes Claude is
standing in the repository that backs the workspace, which was true in the
project the method was born in and false as a general case.

### Breaking

- The project profile moved from `faw.json` at the folder root into
  `.faw/config.json`, next to the state and the receipts. One local file now
  holds the whole project declaration, so nothing about FAW appears in anything
  a third party reads. A leftover `faw.json` triggers a warning and is not read.
- Skills renamed, dropping the redundant prefix: `/faw:faw-classify` is now
  `/faw:classify`, and the same for `profile`, `design`, `validate`,
  `configure`, `backlog`, `roadmap` and `architecture`.
- The two shell hooks merged into `shell_gate.py`, halving the interpreter
  launches per shell command. Manual installations that referenced
  `commit_gate.py` or `pr_gate.py` directly should point at the merged hook.
- `artifacts_in` was removed from the documentation. It was promised and never
  read by any code. Its use case is covered by the model itself now: run FAW
  from a local folder, and nothing internal gets published.

### Added

- `OPERATION` tier for running what already exists: backfills, reruns,
  on-demand refreshes. One checkpoint agreeing what runs, against what, and the
  expected delta; the exit compares the real delta against the expected one.
- Self-check canaries for `verify_brief.py` and `verify_platform.py`. Every
  verifier now has one.
- The per-turn context names the real path of the FAW scripts, so the agent
  does not have to resolve it from a placeholder.
- CI runs the self-check on every push and pull request.

### Fixed

- Work reaching PUBLICATION in a folder without git was permanently stuck: the
  git gates failed, and neither pausing nor abandoning was allowed there. The
  git gates now pass with a note when there is no repository, and pausing
  during publication is allowed, because waiting for a pull request review is
  part of publishing.
- The pull request gate could not read the body of `az repos pr` commands. az
  has no `--body`; it uses `--description` with multiple space-separated
  values, checked against the CLI reference. The gate warned instead of
  blocking.
- The commit gate ran on every repository, with or without `.faw/`,
  contradicting the opt-in the manifest promises. It now honors it.
- The guide and the validate skill showed `--gate contract="ok"` and
  `--gate schema="ok"`, teaching that machine gates accept declarations. They
  do not; the receipts are what satisfies them.
- The validator agent had every tool available while its contract said it does
  not fix. The edit tools are now withheld from it.

## 3.0.0 - 2026-08-19

The project translated to English in full: documentation, rules, skills, hook
messages, code identifiers and the contract data formats. Phases, tiers, gates
and the state machine CLI renamed with it. The method stated plainly as built
for Claude Code.

## 2.x - 2026-08

Published as a public repository. The method generalized away from its origin:
organization detection removed, every governed repository treated as client
surface, project specifics declared in local configuration, the MCP write gate
added, and the state machine made enforceable through hooks.
