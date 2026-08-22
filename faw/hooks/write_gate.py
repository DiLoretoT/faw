#!/usr/bin/env python3
"""
PreToolUse hook over file edits: makes the phases mandatory rather than optional.

It does two things.

**Denies the first write when no work has been classified.** Without it, the
state machine only bit if the agent chose to call it, so a whole artifact could
be built without ever registering the work. Skipping classification stops being
a silent omission.

**Denies writes while the phase is PROFILING.** Profiling is read-only by
definition. This cannot be achieved with a skill's tool restrictions: the
official documentation states that such a restriction clears when the next
message is sent, so it cannot hold for the length of a phase. A hook can.

The output format follows the documented shape for a PreToolUse decision. The
JSON form is used rather than exit code 2 so the reason reaches Claude as
structured data instead of error text.

WHAT THIS HOOK DOES NOT COVER, stated plainly: writing a file from the shell
through redirection or a heredoc does not go through the edit tools, so it does
not reach this hook. As with code running inside a Spark session, the method
detects there but does not prevent. Claiming otherwise would be lying about a
gate.

Opt-in: it does nothing unless the project has a `.faw/` directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

# Real path of THIS installation, so the message can give the exact command
# without assuming where the plugin was cloned or cached.
STATE_PY = Path(__file__).resolve().parent.parent.parent / "scripts" / "state.py"

# Paths that can always be written: the method's own receipts and state. Without
# this exception PROFILING could not produce its receipt and the classification
# could not be registered, so the gate would block itself.
FREE_PREFIXES = (".faw", "docs/faw")


def _target(data: dict) -> str:
    ti = data.get("tool_input") or {}
    return ti.get("file_path") or ti.get("notebook_path") or ""


def _outside_repo(repo: Path, target: str) -> bool:
    """FAW governs the repository, not the disk.

    A file whose target falls outside the repository root is not an artifact of
    the project, so the gate does not apply to it. Without this check, any write
    to an external path would be blocked merely because the process has its
    working directory inside a governed repository. Blocking a personal note or a
    temporary script protects nothing and makes the gate look arbitrary.

    If there is no readable target, False is returned: the case cannot be decided
    in favor, and when in doubt evaluation continues.
    """
    if not target:
        return False
    try:
        Path(target).resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        return True
    return False


def _is_free(repo: Path, target: str) -> bool:
    """Paths belonging to the method itself: always writable."""
    if not target:
        return False
    try:
        rel = Path(target).resolve().relative_to(repo.resolve()).as_posix()
    except (ValueError, OSError):
        return False  # anything outside the repo is handled by _outside_repo
    return any(rel == p or rel.startswith(p + "/") for p in FREE_PREFIXES)


def main() -> int:
    common.prepare_output()

    data = common.payload()
    if data is None:
        return 0

    repo = common.root(data)
    if repo is None:
        return 0

    target = _target(data)
    if _outside_repo(repo, target):
        return 0
    if _is_free(repo, target):
        return 0

    state = common.read_state(repo)
    phase = common.phase_of(state)

    if not state or phase in (None, "IDLE"):
        return common.deny(
            "FAW: write denied because no work has been classified.\n"
            "Classification has to be closed first: restate the request in one sentence, "
            "assign a tier, define what is in and what is NOT, and wait for the user's "
            "approval.\n"
            "Then register it:\n"
            f"  python {STATE_PY} start --tier <TIER> --title \"<title>\"\n"
            "If this is a QUESTION and touches nothing, no classification is needed: "
            "answer without writing."
        )

    if phase == "CLASSIFICATION":
        # Gap found by testing rather than reading: the first version only denied
        # in IDLE and PROFILING, so running `start` was enough to write anything,
        # which meant skipping the first checkpoint with a single command.
        # CLASSIFICATION produces an agreement in conversation, not artifacts.
        return common.deny(
            "FAW: write denied because the phase is CLASSIFICATION, which is closed by "
            "talking rather than building.\n"
            "Still missing: agree on tier and scope with the user, wait for their "
            "approval, and only then move phase:\n"
            f"  python {STATE_PY} move --to <PHASE> --gate user_confirmation=\"...\"\n"
            "One exception can be written here: docs/faw/reports/<report>/brief.md for the "
            "REPORT tier."
        )

    if phase == "PROFILING":
        return common.deny(
            "FAW: write denied because the phase is PROFILING, which is read-only.\n"
            "The profiling receipt itself can be written: it goes in "
            "docs/faw/<ticket>/profiling.md, with every number accompanied by the query "
            "that produced it.\n"
            "If writing to the platform is genuinely required in order to profile, that "
            "needs explicit approval from the user in this turn, and then a phase change."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
