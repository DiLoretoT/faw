#!/usr/bin/env python3
"""
The `metadata` gate: reads the complete diff and fails if it touches protected
configuration without declaring it.

The metadata block of a notebook lives at the top of the file. Reviewing a diff
by looking only at the lines that changed in the body, or at a summary such as
"-50 +2", leaves that block out of frame. A commit can then be approved as a
cosmetic change and lose the default lakehouse without anyone noticing, which
leaves the notebook unable to run. This reads the whole diff.

It is the strongest gate in the method: it runs git locally and does not depend
on anyone declaring anything.

Usage
-----
  python verify_diff.py                        # working tree against HEAD
  python verify_diff.py --range eaeadf0..HEAD  # between two commits
  python verify_diff.py --allow-metadata "intentional lakehouse change"

Exit: 0 if it passes, 1 if protected metadata is touched without permission,
2 if git fails.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import receipts  # noqa: E402

# Metadata keys whose appearance in a diff is never cosmetic. Losing any of them
# breaks the artifact silently.
PROTECTED = [
    "default_lakehouse",
    "default_lakehouse_name",
    "default_lakehouse_workspace_id",
    "known_lakehouses",
    "dependencies",
    "environmentId",
    "environment",
    "workspaceId",
    "lakehouseId",
    "connectionId",
    "logicalId",
]

# Files whose mere presence in the diff signals touched metadata, without
# depending on their content matching a PROTECTED key. A full replacement of the
# file, or a content format this key list does not cover, is still caught by the
# file name.
PROTECTED_FILES = {
    ".platform",
    "lakehouse.metadata.json",
    "shortcuts.metadata.json",
    "alm.settings.json",
}

RE_HEADER = re.compile(r"^(diff --git|index |--- |\+\+\+ |@@ )")

# The key has to appear as an object key, not as a substring inside a comment.
# Without this, a comment mentioning "environment" produced a false positive.
RE_PROTECTED = re.compile(
    r"""["']?\b(""" + "|".join(re.escape(k) for k in PROTECTED) + r""")\b["']?\s*:"""
)


def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(["git"] + args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("ERROR: git was not found on PATH", file=sys.stderr)
        sys.exit(2)
    if out.returncode != 0:
        print(f"ERROR: git {' '.join(args)} failed:\n{out.stderr}", file=sys.stderr)
        sys.exit(2)
    return out.stdout


def get_diff(commit_range: str | None) -> str:
    if commit_range:
        return _git(["diff", commit_range])
    # With no range: everything that is not in HEAD, staged and unstaged.
    return _git(["diff", "HEAD"])


def analyze(diff: str) -> tuple[dict[str, list[str]], int, int]:
    """Returns (findings per file, added lines, removed lines)."""
    findings: dict[str, list[str]] = {}
    current_file = "(unknown)"
    protected_by_name = False
    has_content_change = False
    added = removed = 0

    def _close_previous_file() -> None:
        # A file protected by name is reported even when no line matches
        # PROTECTED: a full replacement, or a content format that key list does
        # not cover, must not pass for free.
        if protected_by_name and has_content_change and current_file not in findings:
            findings[current_file] = ["(file protected by name: any change to it is "
                                      "treated as non-cosmetic)"]

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            _close_previous_file()
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else line
            protected_by_name = Path(current_file).name in PROTECTED_FILES
            has_content_change = False
            continue
        if RE_HEADER.match(line):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
        else:
            continue

        has_content_change = True

        if RE_PROTECTED.search(line):
            findings.setdefault(current_file, []).append(line.rstrip())

    _close_previous_file()
    return findings, added, removed


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW metadata gate")
    p.add_argument("--range", help="commit range, e.g. abc123..HEAD")
    p.add_argument("--allow-metadata", metavar="REASON",
                   help="declares that the metadata change is intentional")
    args = p.parse_args()

    scope = args.range or "working tree against HEAD"
    diff = get_diff(args.range)
    if not diff.strip():
        print("\n  No changes to inspect.\n  PASS\n")
        receipts.issue("metadata", "verify_diff.py", [], f"{scope}: no changes")
        return 0

    findings, added, removed = analyze(diff)

    print(f"\n=== Metadata: {scope} ===")
    print(f"  lines: +{added} -{removed}")

    if not findings:
        print("  protected metadata: unchanged")
        print("\n  PASS\n")
        receipts.issue("metadata", "verify_diff.py", [],
                       f"{scope}: +{added} -{removed}, metadata intact")
        return 0

    total = sum(len(v) for v in findings.values())
    print(f"  protected metadata: {total} lines across {len(findings)} files\n")
    for file_name, lines in findings.items():
        print(f"  {file_name}")
        for l in lines[:12]:
            print(f"      {l[:120]}")
        if len(lines) > 12:
            print(f"      ... and {len(lines) - 12} more")
        print()

    if args.allow_metadata:
        print(f"  Declared intentional: {args.allow_metadata}")
        print("\n  PASS (declared)\n")
        # The bypass stays IN the receipt: whoever looks later at why a metadata
        # gate passed with changes finds the reason that was given.
        receipts.issue("metadata", "verify_diff.py --allow-metadata", [],
                       f"{scope}: {total} metadata lines across {len(findings)} files, "
                       f"DECLARED INTENTIONAL: {args.allow_metadata}")
        return 0

    print("  This diff is NOT cosmetic: it touches metadata the artifact needs to run.")
    print("  If the change is intentional, run again with:")
    print('      --allow-metadata "reason"')
    print("\n  FAIL\n")
    receipts.invalidate("metadata")
    return 1


if __name__ == "__main__":
    sys.exit(main())
