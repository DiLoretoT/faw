#!/usr/bin/env python3
"""
Shared pieces for the hooks: read the input, read the state, deny an action.

Every hook receives the same JSON on stdin and answers in the same format.
Keeping that mechanism in one place prevents a fix from being applied to one
hook and not the others, which is how one gate silently ends up behaving
differently from the rest.

The encoding detail is not cosmetic. On Windows, stdout defaults to cp1252, and
a character outside that set crashes the process. A hook that crashes exits with
a non-zero code, and Claude Code treats that as *non-blocking*: a broken hook
looks exactly like a hook that approved the action. That is why stdin is read as
bytes and decoded explicitly, and stdout is reconfigured to UTF-8.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import project  # noqa: E402


def prepare_output() -> None:
    """Force UTF-8 on stdout. Silent if the runtime does not allow it."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def payload() -> dict | None:
    """The JSON sent by Claude Code, or None if it cannot be parsed.

    Returning None means failing open, and that is deliberate: a parsing error
    in the hook must not block the user's work. The gate exists to catch a
    specific mistake, not to become the point of failure itself.
    """
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def active(repo: Path) -> bool:
    """Whether `.faw/` sits directly in this folder.

    The narrow check. Prefer `root()`, which answers the question the hooks
    actually have: *is there* a governed folder for this call, and which one.
    """
    return (repo / ".faw").is_dir()


def root(data: dict | None) -> Path | None:
    """The governed working folder for this call, or None if there is none.

    Every hook needs the same answer, so it is resolved once here. The reason is
    the one stated at the top of this module: a check duplicated per hook is how
    one gate ends up behaving differently from the rest. That had already
    happened — four hooks called `active()` while `inject_context` inlined the
    same condition, so a fix to one would have missed the other.
    """
    return project.root((data or {}).get("cwd"))


def read_state(repo: Path) -> dict | None:
    """Last entry in `.faw/state.jsonl`, or None if no work is open.

    The file is an event log, not a document: the current state is the last valid
    line. Unreadable lines are skipped rather than aborting, so a partially
    written file does not leave the method without state.
    """
    f = repo / ".faw" / "state.jsonl"
    if not f.exists():
        return None
    last = None
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    return last


def phase_of(state: dict | None) -> str | None:
    """Name of the current phase."""
    if not state:
        return None
    return state.get("phase")


def deny(reason: str) -> int:
    """Deny the call and explain why, in the format the hook event expects.

    The JSON form is used instead of exit code 2 because the reason reaches
    Claude as structured data rather than as error text, which is the difference
    between an agent that corrects course and one that retries the same thing.
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    return 0


def consume_override(repo: Path, name: str) -> str | None:
    """Read and delete a single-use authorization file.

    The file is deleted on read so that a one-off exception does not become a
    standing permission nobody remembers granting. Returns the stated reason, or
    None if the file is missing or empty.
    """
    f = repo / ".faw" / name
    if not f.exists():
        return None
    try:
        reason = f.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    if not reason:
        return None
    f.unlink()
    return reason
