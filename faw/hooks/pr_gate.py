#!/usr/bin/env python3
"""
PreToolUse hook over shell commands: runs the client-surface checklist over the
body of a pull request BEFORE the pull request exists.

## Why it exists

A rule written in `rules/client-surface.md` does not hold if nothing applies it
at the moment of writing. The body of a pull request tends to grow with design
reasoning, open business findings and figures that raise questions for the
reader, even when the rule says explicitly that none of that belongs there. This
gate runs before the pull request exists, so it does not depend on anyone
remembering it.

FAW does not distinguish own repositories from client repositories: the body of
a pull request is always written as if the recipient of the repository were
going to read it.

## What it checks

1. Length: more than TEXT_LIMIT lines of prose is too much. Tables, bullets and
   code blocks do NOT count -- the technical detail is welcome; the paragraphs of
   reasoning are the problem.
2. AI attribution, which is not allowed without exception.
3. In-house methodology and names of other clients or internal repositories.
4. Sections that restate what is already assumed: validation and deployment.
5. Referring to the client in the third person, and assigning tasks to their
   people.

Opt-in: it only acts if the project has `.faw/`, and only on the commands that
create or edit a pull request.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import surface  # noqa: E402

TEXT_LIMIT = 8

# The two command line clients that create or edit a pull request. Covering only
# one left the gate with no effect in any project that used the other, and with
# no warning: the gate was not bypassed, it simply did not exist there.
PR_COMMAND = re.compile(r"\bgh\s+pr\s+(create|edit)\b"
                        r"|\baz\s+repos\s+pr\s+(create|update)\b")

# This applies to the body of a pull request, not to the files: a notebook may
# well document how something was validated. That is why it lives here and not
# in surface.py.
REDUNDANT_SECTION = re.compile(r"^#+\s*(validation|deployment|testing)",
                               re.IGNORECASE | re.MULTILINE)


def _body(command: str, repo: Path) -> str | None:
    """Extract the pull request body from the command.

    Covers `--body 'x'`, `--body "x"`, `--body=x`, the heredoc form of
    `--body-file -`, and `--body-file <path>`.

    Returning None for `--body-file` would switch the gate off silently: a pull
    request created with a heredoc would never be checked, while the same content
    passed with `--body` would be blocked. The heredoc content IS in the command
    string; it only has to be read.
    """
    for rx in (
        r"--body\s*=\s*'((?:[^'\\]|\\.)*)'",
        r'--body\s*=\s*"((?:[^"\\]|\\.)*)"',
        r"--body\s+'((?:[^'\\]|\\.)*)'",
        r'--body\s+"((?:[^"\\]|\\.)*)"',
    ):
        m = re.search(rx, command, re.DOTALL)
        if m:
            return m.group(1)

    # --body-file - <<'EOF' ... EOF   (or <<EOF, or any delimiter)
    m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n(.*?)\n\1\s*$",
                  command, re.DOTALL | re.MULTILINE)
    if m:
        return m.group(2)

    # --body-file <path>
    m = re.search(r"--body-file[\s=]+(?!-\s)(['\"]?)([^\s'\"]+)\1", command)
    if m:
        path = Path(m.group(2))
        if not path.is_absolute():
            path = repo / path
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError:
            return None

    return None


def _prose_lines(body: str) -> int:
    """Count running prose only: headings, tables, bullets, code and blanks are ignored."""
    n = 0
    in_code = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            continue
        if s.startswith("#") or s.startswith("|") or s.startswith(("-", "*", ">")):
            continue
        if re.match(r"^\d+[\.\)]\s", s):
            continue
        n += 1
    return n


def main() -> int:
    common.prepare_output()

    data = common.payload()
    if data is None:
        return 0

    repo = Path(data.get("cwd") or ".")
    if not common.active(repo):
        return 0

    command = (data.get("tool_input") or {}).get("command", "") or ""
    if not PR_COMMAND.search(command):
        return 0

    body = _body(command, repo)
    if body is None:
        # There are still ways of passing a body that cannot be read from the
        # command, such as a variable or a pipe. Those get a warning rather than
        # a block, because the commit already went through the surface gate over
        # the files: this is no longer the only line of defense.
        print("[faw] Could not read this pull request body to check it against "
              "client-surface.md. Check by hand: at most ~8 lines of prose, no AI "
              "attribution, no in-house methodology, no validation or deployment "
              "sections, and no referring to the client in the third person.",
              file=sys.stderr)
        return 0

    failures: list[str] = []

    n = _prose_lines(body)
    if n > TEXT_LIMIT:
        failures.append(f"{n} lines of prose (limit {TEXT_LIMIT}). Tables and bullets do not "
                        f"count: the technical detail is welcome, the paragraphs of "
                        f"reasoning are not.")

    for reason, fragment in surface.review(body, repo):
        failures.append(f"{reason}  -> \"{fragment[:60]}\"")

    m_section = REDUNDANT_SECTION.search(body)
    if m_section:
        failures.append("a 'validation' or 'deployment' section: that something was "
                        "validated is assumed, and the deployment steps are run by the "
                        f"user  -> \"{m_section.group(0)[:60]}\"")

    if not failures:
        return 0

    return common.deny(
        "FAW: pull request blocked by the client-surface checklist "
        "(rules/client-surface.md).\n"
        "Every repository FAW governs is treated as client surface: what is written here "
        "is read by the recipient of the repository.\n\n"
        + "\n".join(f"  - {f}" for f in failures)
        + "\n\nA body that works: one sentence on what this is and what it is for, a table "
          "of data sources, the contents in bullets, and one line of rationale only if the "
          "reviewer needs it.\nLong reasoning goes in the commit message. Business findings "
          "go to the internal tracker."
    )


if __name__ == "__main__":
    sys.exit(main())
