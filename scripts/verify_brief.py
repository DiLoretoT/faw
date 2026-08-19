#!/usr/bin/env python3
"""
The `brief` gate.

Without it, "unconstrained building" in the REPORT tier reads as "nothing needs
to be asked": the agent can end up inferring the scope from the semantic model
instead of agreeing an objective, an audience and the questions the report has to
answer with the user.

The REPORT tier used to enter BUILD with no gates at all. The official planning
skill for reports requires the opposite for a new report: define, inspect,
specify, approve, and only then build. FAW declares those skills as the authority
on mechanics, so leaving the entrance ungated contradicted them.

Why this is a `machine` gate and not a `receipt`: a receipt only checks that the
file exists and weighs more than 200 bytes, and an unfilled template satisfies
that. This script checks that each section has real content and that no template
placeholders survive.

Usage
-----
  python verify_brief.py --ticket <TICKET>
  python verify_brief.py --brief docs/faw/<TICKET>/brief.md

Exit: 0 if the brief is complete and a receipt is issued, 1 if something is
missing, 2 if the inputs are wrong.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import receipts  # noqa: E402

# Each section with the minimum useful content required, in characters. These are
# not arbitrary numbers: a single department name is not an audience, and "see
# balances" is not an objective.
SECTIONS = {
    "objective": 60,
    "audience": 40,
    "questions": 80,
    "out of scope": 30,
    "data source": 30,
}

# Placeholders left by the template. If they survive, the brief was not filled in.
#
# DOTALL and no 60-character ceiling, on purpose: an earlier version used a
# narrow pattern and the UNFILLED template passed almost the whole gate. Its
# placeholders are multi-line paragraphs, they did not fit the ceiling, they did
# not match, and their length counted as real content. Found by testing, not by
# reading. It is the same pattern the gate exists to catch: something that looks
# verified and is not.
RE_PLACEHOLDER = re.compile(
    r"<[^<>]{3,600}>|\bTODO\b|\bXXX\b|\bfill in\b",
    re.IGNORECASE | re.DOTALL,
)

# A business question ends in a question mark. Three are required: with fewer
# than three there is no report, there is a visual.
MIN_QUESTIONS = 3


def _sections(text: str) -> dict[str, str]:
    """Split the markdown by headings and return {normalized title: body}."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            title = m.group(1).strip().lower()
            title = re.sub(r"^\d+[\.\)]\s*", "", title)   # "1. Objective" -> "objective"
            current = title
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def _match_section(sections: dict[str, str], key: str) -> tuple[str, str] | None:
    for title, body in sections.items():
        if key in title:
            return title, body
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW brief gate (REPORT tier)")
    p.add_argument("--ticket", help="ticket; looks for docs/faw/<ticket>/brief.md")
    p.add_argument("--brief", type=Path, help="explicit path to the brief")
    a = p.parse_args()

    if a.brief:
        path = a.brief
    elif a.ticket:
        path = Path("docs") / "faw" / a.ticket / "brief.md"
    else:
        print("ERROR: --ticket or --brief is required", file=sys.stderr)
        return 2

    print(f"\n=== Brief: {path} ===")

    if not path.exists():
        print(f"\n  [ERROR] {path} does not exist.\n"
              f"  Before building a report, what it exists for has to be agreed with the "
              f"user.\n"
              f"  Template: faw/contracts/TEMPLATE.brief.md\n\n  FAIL\n")
        receipts.invalidate("brief")
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _sections(text)
    failures: list[str] = []

    for key, minimum in SECTIONS.items():
        found = _match_section(sections, key)
        if found is None:
            failures.append(f"the '{key}' section is missing")
            continue
        title, body = found
        # Placeholders are removed before measuring, so that a brief full of
        # "<fill in>" does not pass by sheer character count.
        clean = RE_PLACEHOLDER.sub("", body).strip()
        if len(clean) < minimum:
            failures.append(f"'{title}' has {len(clean)} useful characters, "
                            f"at least {minimum} are expected")
        if RE_PLACEHOLDER.search(body):
            failures.append(f"'{title}' still has unfilled template placeholders")

    questions = _match_section(sections, "questions")
    if questions:
        n = questions[1].count("?")
        if n < MIN_QUESTIONS:
            failures.append(f"'questions' declares {n} questions and {MIN_QUESTIONS} are "
                            f"required (each one ends in '?')")

    print(f"  sections found: {len(sections)}")

    if failures:
        print(f"\n  [ERROR] the brief is incomplete:")
        for f in failures:
            print(f"      {f}")
        print("\n  This does not get filled in on its own: these are questions for the "
              "user.\n\n  FAIL\n")
        receipts.invalidate("brief")
        return 1

    print("\n  PASS\n")
    receipts.issue("brief", "verify_brief.py", [path],
                   f"complete brief at {path} ({len(sections)} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
