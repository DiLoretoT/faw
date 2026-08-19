#!/usr/bin/env python3
"""
Project profile: the things FAW cannot know on its own and should not assume.

## The problem

A workflow that runs on top of a data platform touches infrastructure that
differs between installations: where tickets live, whether there is a
development environment separate from production, whether code can be executed
against the tenant. Writing those answers into the method makes it correct for
one project and wrong for every other one.

## Two files, because they have two different lifecycles

`faw.json`, at the root of the working repository, **is versioned**. It holds
the process rules of the project: which ticket system is in use, whether there
is a development environment, how changes reach production. Those are team
decisions, not machine settings. They have to travel with the repository, be
reviewed in a pull request, and be the same for everyone. A profile that lives
on one machine produces two people working under different rules with nothing
to detect it.

`.faw/config.json` **is not versioned**. It holds what cannot be published or
shared: names of people, internal identifiers, local paths. Keeping both in one
file would force a choice between publishing names and hiding rules.

## How missing values are resolved

By the option that asks for more control, never by the one that allows more.
With no environments declared, FAW assumes there is a single one and treats it
as production, so every write to the platform requires the reason in writing
before it runs.

The asymmetry is what justifies it: a stricter default costs an authorization
the user was going to give anyway, while a looser one writes to production
without asking.

That default is not pessimism. Microsoft documents deployment on a single
workspace as a valid, supported pattern for smaller organizations, and in that
pattern deployment pipelines do not exist because they need several workspaces.
A project without a separate development environment is a normal case.

## Every key changes something

A key that only produced different wording would not be here. `environments.dev`
decides whether authorization to write is spoken or has to be written down
before running. `tickets.system` decides where the work identifier comes from
and whether there is an external backlog to read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Process profile, versioned with the working repository.
PROFILE_FILE = "faw.json"

# Local data that is never published. Same file the surface gate reads.
LOCAL_FILE = "config.json"

# Recognized ticket systems. `internal` is FAW's own registry, which depends on
# nothing external; `none` turns the notion of an external ticket off and keeps
# only the identifier that receipt paths need.
TICKET_SYSTEMS = ("ado", "jira", "github", "internal", "none")

# Which MCP server knows how to operate each system. If it is connected in the
# session, the agent reads and updates tickets there. If it is not, the system
# is still the declared one and the user operates it by hand.
MCP_BY_SYSTEM = {
    "ado": "mcp__ado__*",
    "github": "mcp__github__*",
}

PROMOTIONS = ("deployment-pipeline", "git", "manual", "none")

DEFAULTS = {
    "tickets": {"system": "internal", "project": None, "organization": None},
    "environments": {"dev": False, "prd": True, "promotion": "manual"},
    "channel": {"livy": False, "control_table": None, "microsoft_skills": None,
                "mcp_servers": None},
}


def _read(path: Path, label: str) -> dict:
    """Read a configuration file. An unreadable file warns instead of being ignored.

    Degrading silently on malformed JSON is the failure mode principle 4 forbids:
    the method would keep running with half of its rules and everything would
    look normal. An empty dict is returned so work is not blocked, but the
    warning goes to stderr so the error is visible when it happens.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[faw] {label} exists but could not be read ({e}). Continuing with "
              f"the default values, which are the strictest ones. Fix the file: "
              f"until then its rules are not being applied.", file=sys.stderr)
        return {}
    if not isinstance(raw, dict):
        print(f"[faw] {label} does not contain a JSON object. Ignored.", file=sys.stderr)
        return {}
    return raw


def _merge(declared: dict, default: dict) -> dict:
    """Fill in missing keys without overriding what was declared.

    Key by key rather than section by section: declaring `environments.dev` must
    not erase `environments.promotion`. A partial profile is the normal case.
    """
    out = dict(default)
    if isinstance(declared, dict):
        for k, v in declared.items():
            if v is not None:
                out[k] = v
    return out


def _warn_unknown_keys(raw: dict) -> None:
    """A key FAW does not understand is reported instead of ignored.

    A misspelled `enviroments` must not pass as a valid profile: the rule the
    user believed they declared would not be applied, and nothing would say so.
    """
    for section in raw:
        if section in DEFAULTS:
            unknown = set(raw[section] or {}) - set(DEFAULTS[section])
            if unknown:
                print(f"[faw] {PROFILE_FILE}: unrecognized keys in '{section}': "
                      f"{', '.join(sorted(unknown))}. Not applied.", file=sys.stderr)
        else:
            print(f"[faw] {PROFILE_FILE}: unrecognized section '{section}'. Not applied.",
                  file=sys.stderr)


def profile(repo: Path) -> dict:
    """Normalized project profile with the strict defaults applied."""
    raw = _read(repo / PROFILE_FILE, PROFILE_FILE)
    _warn_unknown_keys(raw)

    p = {section: _merge(raw.get(section) or {}, DEFAULTS[section])
         for section in DEFAULTS}

    system = str(p["tickets"].get("system") or "").strip().lower()
    p["tickets"]["system"] = system if system in TICKET_SYSTEMS else "internal"

    promotion = str(p["environments"].get("promotion") or "").strip().lower()
    p["environments"]["promotion"] = promotion if promotion in PROMOTIONS else "manual"

    p["environments"]["dev"] = bool(p["environments"].get("dev"))
    p["environments"]["prd"] = bool(p["environments"].get("prd", True))
    p["channel"]["livy"] = bool(p["channel"].get("livy"))

    p["declared"] = bool(raw)
    return p


def local(repo: Path) -> dict:
    """Local, unversioned data: names, internal literals, paths on this machine."""
    return _read(repo / ".faw" / LOCAL_FILE, ".faw/" + LOCAL_FILE)


def single_environment(p: dict) -> bool:
    """True when there is no development environment separate from production."""
    return not p["environments"]["dev"]


def requires_written_authorization(p: dict) -> bool:
    """Whether every write to the platform must state its reason in writing first.

    This is what `environments.dev` actually changes. With a test environment,
    being wrong is cheap and the spoken authorization of the turn is enough.
    Without one, every write lands on data someone is using, and authorization
    moves from something the agent states to a file the hook can check.
    """
    return single_environment(p)


def write_rule(p: dict) -> str:
    """The authorization rule that applies to this project, in one line."""
    if single_environment(p):
        return ("Single environment, treated as production: every write to the platform "
                "needs its reason written to .faw/tenant-authorization.txt before it runs.")
    return ("Writes to development: explicit approval from the user in the turn. "
            "Changes in production: explicit approval, always.")


def run_record(p: dict) -> str:
    """Where a run that wrote to the platform leaves its record."""
    table = p["channel"].get("control_table")
    if table:
        return f"Record the run in {table} and in the ticket receipt."
    return "Record the run in the ticket receipt."


def ticket_mcp(p: dict) -> str | None:
    """MCP server that operates the declared ticket system, if a known one exists."""
    return MCP_BY_SYSTEM.get(p["tickets"]["system"])


def context_line(p: dict) -> str:
    """One line with what changes decisions in this project, injected per turn.

    One line, and only what changes what the agent may do without asking. The
    hook that uses it states its own budget: anything that narrates on every
    turn trains the reader to skip it.
    """
    parts = [write_rule(p)]
    system = p["tickets"]["system"]
    if system == "internal":
        parts.append("Tickets: FAW internal registry (docs/faw/tickets/).")
    elif system != "none":
        mcp = ticket_mcp(p)
        parts.append(f"Tickets: {system}" + (f" (via {mcp} when available)." if mcp else "."))
    return " ".join(parts)
