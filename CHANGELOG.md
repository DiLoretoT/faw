# Changelog

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
