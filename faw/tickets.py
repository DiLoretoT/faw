#!/usr/bin/env python3
"""
Internal ticket registry: the tracker that exists when there is no tracker.

## Why it is needed

The method needs a work identifier to name its receipts and to make the question
"where were we" answerable after the session is closed. That identifier usually
comes from an external tracker, but requiring one would turn a project
management tool into an installation prerequisite: whoever does not use any
would end up inventing identifiers to satisfy the method, and an invented
identifier refers to nothing.

This module solves that case without depending on any service. A ticket is a
markdown file in the working repository, and git provides the history: whoever
wants to know how the scope of a piece of work changed reads the file log. That
is what an external tracker offers and a loose file does not.

## What a project with a tracker gains

None of this replaces it. If the profile declares `ado`, `jira` or `github`, the
identifier comes from there and this registry is unused. The difference is
whether an MCP server exists for that tracker: with one, the agent reads and
updates the ticket directly; without one, the tracker is still the source of the
identifier and the user operates the tool. The method works the same either way,
because the only thing it needs from a ticket is its identifier.

## Why tickets are versioned and pass through the surface gate

A ticket contains, by its nature, open questions and tasks assigned to people.
That is exactly the content that should not reach a repository a third party
reads. The registry lives under `docs/faw/tickets/`, which the surface gate does
inspect, unlike the rest of `docs/faw/`. If the reader of the repository should
not see tickets at all, the project declares a different artifact root.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

TICKETS_DIR = Path("docs") / "faw" / "tickets"

STATES = ("open", "in-progress", "paused", "closed", "abandoned")

# An identifier ends up as a directory name (`docs/faw/<id>/`). Characters that
# Windows forbids in a path would break the receipt write at the end of the work,
# when there is nothing left to do about it.
VALID_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def sanitize(identifier: str) -> str | None:
    """Return the identifier if it works as a path name, otherwise None."""
    ident = (identifier or "").strip()
    return ident if VALID_ID.match(ident) else None


def _next_number(repo: Path) -> int:
    """Next free number in the internal registry.

    Computed by reading the existing files rather than storing a counter: a
    counter in a separate file goes out of sync as soon as two people create a
    ticket on different branches, and the conflict shows up somewhere that
    explains nothing.
    """
    d = repo / TICKETS_DIR
    if not d.is_dir():
        return 1
    used = []
    for f in d.glob("T-*.md"):
        m = re.match(r"^T-(\d+)$", f.stem)
        if m:
            used.append(int(m.group(1)))
    return max(used, default=0) + 1


def new_identifier(repo: Path) -> str:
    """Sequential identifier for the internal registry, formatted as `T-007`.

    Sequential rather than derived from the title: an identifier built from text
    has to be sanitized, can collide, and changes when the title is corrected. A
    number has none of those problems and sorts by age.
    """
    return f"T-{_next_number(repo):03d}"


def path_for(repo: Path, identifier: str) -> Path:
    return repo / TICKETS_DIR / f"{identifier}.md"


def create(repo: Path, identifier: str, title: str, tier: str,
           scope: str = "", out_of_scope: str = "") -> Path:
    """Write the ticket with what was agreed during CLASSIFICATION.

    The sections are not decoration: they are the questions the phase has to
    answer. A ticket without "what is out of scope" documents an intention
    rather than a scope, and that is the gap through which work grows without
    anyone deciding it should.
    """
    f = path_for(repo, identifier)
    f.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    f.write_text(
        f"# {identifier} - {title}\n\n"
        f"| | |\n|---|---|\n"
        f"| State | open |\n"
        f"| Tier | {tier} |\n"
        f"| Opened | {today} |\n\n"
        f"## What is being asked\n\n{scope or '<one sentence, restating the request>'}\n\n"
        f"## What is out of scope\n\n{out_of_scope or '<what is explicitly left out>'}\n\n"
        f"## Log\n\n- {today} - opened\n",
        encoding="utf-8",
    )
    return f


def log_event(repo: Path, identifier: str, event: str) -> bool:
    """Append a line to the ticket log. False if the ticket does not exist."""
    f = path_for(repo, identifier)
    if not f.exists():
        return False
    content = f.read_text(encoding="utf-8-sig").rstrip("\n")
    content += f"\n- {date.today().isoformat()} - {event}\n"
    f.write_text(content, encoding="utf-8")
    return True


def set_state(repo: Path, identifier: str, state: str) -> bool:
    """Change the state declared in the header table."""
    if state not in STATES:
        return False
    f = path_for(repo, identifier)
    if not f.exists():
        return False
    content = f.read_text(encoding="utf-8-sig")
    updated = re.sub(r"^\| State \| .* \|$", f"| State | {state} |",
                     content, count=1, flags=re.MULTILINE)
    f.write_text(updated, encoding="utf-8")
    return True


def listing(repo: Path) -> list[tuple[str, str, str]]:
    """Tickets in the internal registry as (identifier, state, title)."""
    d = repo / TICKETS_DIR
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        m_state = re.search(r"^\| State \| (.+?) \|$", text, re.MULTILINE)
        m_title = re.search(r"^# \S+ - (.+)$", text, re.MULTILINE)
        out.append((f.stem,
                    m_state.group(1).strip() if m_state else "?",
                    m_title.group(1).strip() if m_title else ""))
    return out
