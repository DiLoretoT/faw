#!/usr/bin/env python3
"""
Shared module: the checklist in `rules/client-surface.md` expressed as code.

## Why it exists

These patterns used to live inside the pull request gate and applied only to the
body of a pull request. Reviewing only that reviews the summary of the work, not
the work: the same content the gate rejects can still reach the repository
through the committed files -- a note marked as internal, visible in a report
artifact, inside the client's tenant, with nothing checking it.

There are also ways of passing a pull request body that cannot be read as a
simple string, such as a heredoc, and they have to be covered like a literal
argument.

This module centralizes the patterns so both gates apply them: the one on the
pull request and the one on the commit.

The checklist applies to every repository FAW governs. There is no distinction
between own repositories and client repositories: everything is written as if the
recipient of the repository were going to read it. What is specific to each
project -- names of people, internal literals -- is declared in
`.faw/config.json`, which is not versioned.

## False positives, on purpose

`\bthe client\b` also matches a legitimate business use, such as referring to a
client dimension table. Stopping and having the reason declared in an override
file is preferred over letting through a phrase that has already been published.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# Keys in `.faw/config.json`. Both are lists, empty by default: what each project
# does not want leaked is declared by the user, not by the code.
PEOPLE_KEY = "client_people"
LITERALS_KEY = "internal_literals"

# (regex, what to say). Each pattern answers an observed failure mode.
FORBIDDEN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bclaude\b|\bcopilot\b|\banthropic\b|generated with|"
                r"co-authored-by:\s*claude", re.IGNORECASE),
     "AI attribution, which does not belong in a client repository, without exception"),
    (re.compile(r"\bFAW\b|faw-classify|faw-design|FAW\s+gates?"),
     "the internal working method does not belong in a client repository"),
    (re.compile(r"\b(the|our|this) client\b", re.IGNORECASE),
     "refers to the client in the third person, inside their own repository"),
    (re.compile(r"do not share\b|don't share\b|internal use|\binternal:", re.IGNORECASE),
     "a working note marked as internal, written into an artifact the client reads"),
    (re.compile(r"open question|finding for the tracker|take to \w+|"
                r"worth explaining to|coordinate with \w+|confirm with \w+", re.IGNORECASE),
     "an open finding or a task assigned to someone on the client side, which belongs "
     "in the internal tracker"),
]


def _config(repo: Path) -> dict:
    """`.faw/config.json` of the project. Not versioned, so it may not exist."""
    f = repo / ".faw" / "config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}


def patterns(repo: Path) -> list[tuple[re.Pattern[str], str]]:
    """FORBIDDEN plus whatever `.faw/config.json` declares: people and literals."""
    ps = list(FORBIDDEN)
    cfg = _config(repo)
    names = [re.escape(str(p).strip())
             for p in (cfg.get(PEOPLE_KEY) or [])
             if str(p).strip()]
    if names:
        ps.append((
            re.compile(r"\b(" + "|".join(names) + r")\b", re.IGNORECASE),
            "names a person on the client side; names, and the tasks assigned to them, "
            "belong in the internal tracker",
        ))
    literals = [re.escape(str(lit).strip())
                for lit in (cfg.get(LITERALS_KEY) or [])
                if str(lit).strip()]
    if literals:
        ps.append((
            re.compile("|".join(literals), re.IGNORECASE),
            "a literal declared as internal in .faw/config.json: names of other projects, "
            "repositories or in-house methodology do not belong in a published repository",
        ))
    return ps


def review(text: str, repo: Path) -> list[tuple[str, str]]:
    """[(reason, fragment)] for every pattern that matches. Empty list means it passes."""
    findings = []
    for rx, reason in patterns(repo):
        m = rx.search(text)
        if m:
            findings.append((reason, m.group(0)))
    return findings


def added_lines(repo: Path) -> list[tuple[str, int, str]]:
    """Lines the commit ADDS, from the staged diff. Returns (file, number, text).

    Only added lines: whatever was already there is fixed separately, not by
    blocking every commit that happens to touch it.

    `.faw/` is excluded because it is not versioned, and so is `docs/faw/`,
    which holds the method's own artifacts. The exception to that exception is
    `docs/faw/tickets/`, which IS inspected: a ticket contains open questions and
    tasks assigned to people by its very nature, which is precisely the content
    that should not reach a repository a third party reads. Exempting it for
    living under `docs/faw/` would open the widest door exactly where the most
    sensitive material passes.
    """
    try:
        r = subprocess.run(["git", "diff", "--cached", "--unified=0", "--no-color"],
                           cwd=str(repo), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []

    out: list[tuple[str, int, str]] = []
    current_file = ""
    number = 0
    for line in r.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            number = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            exempt = (current_file.startswith((".faw/", "docs/faw/"))
                      and not current_file.startswith("docs/faw/tickets/"))
            if current_file and current_file != "/dev/null" and not exempt:
                out.append((current_file, number, line[1:]))
            number += 1
    return out


def review_staged_diff(repo: Path) -> list[tuple[str, int, str, str]]:
    """Apply the patterns to the lines the commit adds.

    Returns (file, number, reason, fragment). Empty list means it passes.
    """
    ps = patterns(repo)
    findings = []
    for file_name, number, text in added_lines(repo):
        for rx, reason in ps:
            m = rx.search(text)
            if m:
                findings.append((file_name, number, reason, m.group(0)))
                break
    return findings
