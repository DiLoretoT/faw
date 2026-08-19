#!/usr/bin/env python3
"""
Project profile: the things FAW cannot know on its own and should not assume.

## Where Claude stands, and why the profile lives where it lives

Work on a data platform happens in three different places. The **tenant**, where
the artifacts run. The **repository that backs the workspace**, when git
integration is on, often synced on the service side without anyone cloning it.
And the **working folder**, which is wherever Claude Code is standing. A local
path on the engineer's machine, git or not, and usually not the backing
repository.

The profile describes the project, so it lives with the working folder, inside
`.faw/config.json`. That directory is already the method's local home. It is not
versioned, so nothing about FAW has to appear in any repository a third party
reads. An earlier version kept the profile in a `faw.json` at the folder root,
which forced publishing the method's presence whenever the folder was a shared
repository. That file is no longer read, and a warning says so if one is found.

## How missing values are resolved

By the option that asks for more control, never by the one that allows more.
With no environments declared, FAW assumes there is a single one and treats it
as production, so every write to the platform requires the reason in writing
before it runs.

The asymmetry is what justifies it. A stricter default costs an authorization
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

The same file also holds `client_people` and `internal_literals`, the two lists
the surface gate reads. One file, local by design, holding everything the
project declares.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The single project file: profile, people and literals. Local by design.
CONFIG_FILE = Path(".faw") / "config.json"

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

# Top-level keys that belong to the surface gate, read by surface.py from the
# same file. Known, so the unknown-key warning does not fire on them.
SURFACE_KEYS = {"client_people", "internal_literals"}


def _read(path: Path, label: str) -> dict:
    """Read a configuration file. An unreadable file warns instead of being ignored.

    Degrading silently on malformed JSON is the failure mode principle 4 forbids.
    The method would keep running with half of its rules and everything would
    look normal. An empty dict is returned so work is not blocked, but the
    warning goes to stderr so the error is visible when it happens.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[faw] {label} exists but could not be read ({e}). Continuing with "
              f"the default values, which are the strictest ones. Fix the file; "
              f"until then its rules are not being applied.", file=sys.stderr)
        return {}
    if not isinstance(raw, dict):
        print(f"[faw] {label} does not contain a JSON object. Ignored.", file=sys.stderr)
        return {}
    return raw


def _merge(declared: dict, default: dict) -> dict:
    """Fill in missing keys without overriding what was declared.

    Key by key rather than section by section. Declaring `environments.dev` must
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

    A misspelled `enviroments` must not pass as a valid profile. The rule the
    user believed they declared would not be applied, and nothing would say so.
    """
    for section in raw:
        if section in DEFAULTS:
            unknown = set(raw[section] or {}) - set(DEFAULTS[section])
            if unknown:
                print(f"[faw] {CONFIG_FILE}: unrecognized keys in '{section}': "
                      f"{', '.join(sorted(unknown))}. Not applied.", file=sys.stderr)
        elif section not in SURFACE_KEYS:
            print(f"[faw] {CONFIG_FILE}: unrecognized section '{section}'. Not applied.",
                  file=sys.stderr)


def profile(repo: Path) -> dict:
    """Normalized project profile with the strict defaults applied."""
    if (repo / "faw.json").exists():
        print("[faw] faw.json at the folder root is no longer read. Move its contents "
              "into .faw/config.json, which is local and never published.",
              file=sys.stderr)

    raw = _read(repo / CONFIG_FILE, str(CONFIG_FILE))
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
        return ("Single environment, treated as production. Every write to the platform "
                "needs its reason written to .faw/tenant-authorization.txt before it runs.")
    return ("Writes to development need explicit approval from the user in the turn. "
            "Changes in production need explicit approval, always.")


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
    hook that uses it states its own budget. Anything that narrates on every
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
