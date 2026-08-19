#!/usr/bin/env python3
"""
PreToolUse hook over shell commands: one process for the two shell gates.

The commit gate and the pull request gate both fire on every shell command, and
they used to be registered as two separate hooks. That meant two interpreter
launches per command, and on Windows the launch is what dominates, at somewhere
between fifty and a hundred and fifty milliseconds each. This reads the payload
once and runs both.

The behavior is the two gates', unchanged. A command that is only a commit is
seen by the commit gate; one that is only a pull request, by the PR gate; a
chained command that is both goes through both, same as when they were separate.

Opt-in: both gates exit without doing anything unless the project has `.faw/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commit_gate  # noqa: E402
import common  # noqa: E402
import pr_gate  # noqa: E402


def main() -> int:
    common.prepare_output()
    data = common.payload()
    if data is None:
        return 0

    # The PR gate denies through JSON on stdout with exit 0; the commit gate
    # blocks through exit 2. Running both preserves each mechanism, and the
    # commit gate's exit code decides the process result, as it did before.
    pr_rc = pr_gate.run(data)
    commit_rc = commit_gate.run(data)
    return commit_rc or pr_rc


if __name__ == "__main__":
    sys.exit(main())
