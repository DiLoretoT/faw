#!/usr/bin/env python3
"""
PreToolUse hook over shell commands: makes the commit gates a real constraint
rather than a convention.

It fires before any shell call. If the command is a `git commit`, it runs three
checks over the diff that is about to be committed, and blocks the call before
the commit exists:

1. `metadata`: the diff does not silently alter protected configuration.
2. `platform`: no invented platform literals reach the repository.
3. `surface`: no content that should not be read by a third party.

Blocking uses exit code 2, which is the documented way for a hook to stop a
command and show the reason to Claude.

This does not replace running the verifiers by hand: it makes skipping them by
omission impossible. What it still cannot inspect is code running inside a Spark
session, which is arbitrary and out of reach of any pre-execution check.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import surface  # noqa: E402

FAW_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFY_DIFF = FAW_ROOT / "scripts" / "verify_diff.py"
VERIFY_PLATFORM = FAW_ROOT / "scripts" / "verify_platform.py"

GIT_COMMIT = re.compile(r"\bgit\s+(?:-[A-Za-z-]+(?:=\S+)?\s+)*commit\b")


def main() -> int:
    data = common.payload()
    if data is None:
        # The input could not be read: fail OPEN. Blocking every commit because
        # of a parsing error in the hook would be a worse failure than the one it
        # is trying to prevent.
        return 0

    command = (data.get("tool_input") or {}).get("command", "") or ""
    if not GIT_COMMIT.search(command):
        return 0  # not a commit, none of our business

    repo = Path(data.get("cwd") or ".")

    if not VERIFY_DIFF.exists():
        print(f"[faw] {VERIFY_DIFF} not found. The commit is allowed without the "
              f"metadata check; the hook needs looking at.", file=sys.stderr)
    else:
        result = subprocess.run(
            [sys.executable, str(VERIFY_DIFF)],
            cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )

        # NOTE: there is no early return here. An earlier version returned as soon
        # as metadata passed, which left the platform gate UNREACHABLE in the
        # normal case of a diff with no protected metadata. That was found by
        # testing, not by reading: the hook failed to block an invented literal.
        # The gates are independent and all of them run every time.
        if result.returncode == 2:
            print(f"[faw] verify_diff.py failed to run:\n{result.stderr}\n"
                  f"Skipping the metadata check; the hook needs looking at.",
                  file=sys.stderr)

        if result.returncode == 1:
            reason = common.consume_override(repo, "metadata-allowed.txt")
            if reason:
                print(f"[faw] protected metadata detected, declared intentional: {reason}",
                      file=sys.stderr)
            else:
                print(
                    "[faw] COMMIT BLOCKED. This diff touches protected metadata "
                    "(default lakehouse, dependencies, environment) without declaring it.\n\n"
                    + result.stdout + "\n"
                    "If the change is intentional:\n"
                    "  1. Run:  python " + str(VERIFY_DIFF) + ' --allow-metadata "reason"\n'
                    "  2. Or write the reason to .faw/metadata-allowed.txt in the repository "
                    "and retry the commit. The file is consumed when used.\n"
                    "     NOTE: this hook runs BEFORE the command. Writing the file and "
                    "committing in the SAME call does not work: when the hook looks, the "
                    "file does not exist yet. It takes two steps.\n",
                    file=sys.stderr,
                )
                return 2

    code = _check_platform(repo)
    if code != 0:
        return code
    return _check_surface(repo)


def _check_surface(repo: Path) -> int:
    """The client-surface checklist applied to the FILES, not to the pull request body.

    Reviewing the body of a pull request is not enough: the content that reaches
    the reader lives in the files, not in the summary of the change. This gate
    reads the staged diff. It applies to every governed repository, because FAW
    does not distinguish own repositories from client repositories.
    """
    findings = surface.review_staged_diff(repo)
    if not findings:
        return 0

    reason = common.consume_override(repo, "surface-allowed.txt")
    if reason:
        print(f"[faw] client surface: {len(findings)} findings, declared intentional: "
              f"{reason}", file=sys.stderr)
        return 0

    detail = "\n".join(
        f"  {file_name}:{number}\n      {why}\n      -> \"{fragment[:70]}\""
        for file_name, number, why, fragment in findings[:12]
    )
    rest = f"\n  ... and {len(findings) - 12} more" if len(findings) > 12 else ""

    print(
        "[faw] COMMIT BLOCKED. The diff adds content that does not belong in a repository "
        "a third party reads (FAW treats every governed repository as client surface).\n\n"
        + detail + rest + "\n\n"
        "What belongs in the repository is what changed and how it was validated. Design "
        "reasoning, open findings, business questions, names of people with tasks assigned "
        "to them, and references to in-house methodology or internal repositories go to the "
        "project's internal tracker (rules/client-surface.md).\n"
        "If this is a false positive, write the reason to .faw/surface-allowed.txt and "
        "retry. NOTE: the hook runs BEFORE the command, so writing the file and committing "
        "in the same call does not work. It takes two steps.\n",
        file=sys.stderr,
    )
    return 2


def _check_platform(repo: Path) -> int:
    """The platform gate at the same moment: over the staged diff, before the
    commit exists.

    Principle 6 already forbids inventing platform literals by analogy. This gate
    enforces it at the moment of writing rather than afterwards.
    """
    if not VERIFY_PLATFORM.exists():
        print(f"[faw] {VERIFY_PLATFORM} not found. The commit is allowed without the "
              f"platform check.", file=sys.stderr)
        return 0

    result = subprocess.run(
        [sys.executable, str(VERIFY_PLATFORM)],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )

    if result.returncode == 0:
        return 0
    if result.returncode != 1:
        print(f"[faw] verify_platform.py failed to run:\n{result.stderr}\n"
              f"The commit is allowed; the hook needs looking at.", file=sys.stderr)
        return 0

    reason = common.consume_override(repo, "platform-allowed.txt")
    if reason:
        print(f"[faw] unverified platform literal, declared intentional: {reason}",
              file=sys.stderr)
        return 0

    print(
        "[faw] COMMIT BLOCKED. The diff contains platform literals with no precedent in "
        "the repository that do not resolve.\n\n" + result.stdout + "\n"
        "A literal invented by analogy can break on the end user's screen. Copy it from a "
        "real artifact, let the tool generate it, or read the official documentation. If "
        "this is a legitimate case, such as working without network access, write the "
        "reason to .faw/platform-allowed.txt and retry.\n"
        "NOTE: the hook runs BEFORE the command, so writing the file and committing in the "
        "same call does not work. It takes two steps.\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
