#!/usr/bin/env python3
"""
The `layout` gate.

What this verifies is the layout **agreement**, not the layout. Whether a matrix
was the right visual, whether the arrangement reads well, whether the colour
carries meaning: none of that is machine-verifiable, and a gate claiming
otherwise would be the thing this method exists to prevent.

What it does check is that the agreement is a real agreement. Every page states
which question from the brief it answers, the navigation is written down, and no
template placeholder survived. The failure it closes is the report that gets
built page by page as it occurs to whoever is building it, precise about
questions nobody asked, with the brief agreed weeks ago and never reread.

Why this is a `machine` gate rather than a `receipt`: a receipt only checks that
a file exists and weighs something, and an unfilled template satisfies that. The
same reasoning as the brief gate, and the same limits.

Usage
-----
  python verify_layout.py --ticket <TICKET>
  python verify_layout.py --layout docs/faw/<TICKET>/layout.md

Exit: 0 if the agreement is complete and a receipt is issued, 1 if something is
missing, 2 if the inputs are wrong.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import project  # noqa: E402
from faw import receipts  # noqa: E402

# Sections required, with the minimum of useful content each one owes, in
# characters. Not arbitrary: "sales by month" is not a page description, and a
# navigation section of ten characters is a heading with nothing under it.
SECTIONS = {
    "pages": 200,
    "navigation": 40,
}

# Placeholders left by the template. Same pattern as the brief gate, including
# DOTALL and no upper bound: the template placeholders are multi-line paragraphs,
# and a narrower pattern let an unfilled template through by counting its own
# instructions as content.
RE_PLACEHOLDER = re.compile(
    r"<[^<>]{3,600}>|\bTODO\b|\bXXX\b|\bfill in\b",
    re.IGNORECASE | re.DOTALL,
)

# A page block starts at a third-level heading. Numbering is optional.
RE_PAGE = re.compile(r"^###\s+(.+)$", re.MULTILINE)

# Every page owes the question it answers. This is the whole point of the gate:
# a page that answers nothing from the brief is a page nobody asked for.
RE_ANSWERS = re.compile(r"^\s*[-*]\s*\*\*Answers:?\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def _sections(text: str) -> dict[str, str]:
    """Split by second-level headings and return {normalized title: body}."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).strip().lower()
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

    p = argparse.ArgumentParser(description="FAW layout agreement gate (REPORT tier)")
    p.add_argument("--ticket", help="ticket; looks for docs/faw/<ticket>/layout.md")
    p.add_argument("--layout", type=Path, help="explicit path to the layout agreement")
    a = p.parse_args()

    root = project.root() or Path.cwd()

    if a.layout:
        path = a.layout if a.layout.is_absolute() else root / a.layout
    elif a.ticket:
        path = root / "docs" / "faw" / a.ticket / "layout.md"
    else:
        print("ERROR: --ticket or --layout is required", file=sys.stderr)
        return 2

    print(f"\n=== Layout agreement: {path} ===")

    if not path.exists():
        print(f"\n  [ERROR] {path} does not exist.\n"
              f"  Before building pages, what they are and which question each one\n"
              f"  answers has to be agreed with the user.\n"
              f"  Template: faw/contracts/TEMPLATE.layout.md\n\n  FAIL\n")
        receipts.invalidate("layout")
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
        clean = RE_PLACEHOLDER.sub("", body).strip()
        if len(clean) < minimum:
            failures.append(f"'{title}' has {len(clean)} useful characters, at least "
                            f"{minimum} are expected")
        if RE_PLACEHOLDER.search(body):
            failures.append(f"'{title}' still has unfilled template placeholders")

    pages_section = _match_section(sections, "pages")
    page_count = 0
    if pages_section:
        body = pages_section[1]
        pages = RE_PAGE.findall(body)
        answers = RE_ANSWERS.findall(body)
        page_count = len(pages)

        if page_count == 0:
            failures.append("no page is declared. A layout agreement with no pages is "
                            "an empty document")
        elif len(answers) < page_count:
            failures.append(f"{page_count} pages declared and {len(answers)} state which "
                            f"question they answer. A page that answers no question from "
                            f"the brief either uncovered one that belongs in the brief, "
                            f"or does not belong in the report")

        for ans in answers:
            if RE_PLACEHOLDER.search(ans) or len(ans.strip()) < 15:
                failures.append(f"a page declares '{ans.strip()[:40]}' as the question it "
                                f"answers, which is not a question")

    print(f"  sections found: {len(sections)}   pages declared: {page_count}")

    if failures:
        print("\n  [ERROR] the layout agreement is incomplete:")
        for f in failures:
            print(f"      {f}")
        print("\n  This does not get filled in on its own. The pages and what each one "
              "answers\n  are agreed with the user before building them.\n\n  FAIL\n")
        receipts.invalidate("layout")
        return 1

    print("\n  PASS\n")
    receipts.issue("layout", "verify_layout.py", [path],
                   f"layout agreement at {path} ({page_count} pages, each with the "
                   f"question it answers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
