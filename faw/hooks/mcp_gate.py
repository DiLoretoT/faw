#!/usr/bin/env python3
"""
PreToolUse hook over MCP tools: extends the phases to writes that never touch a
file.

## The gap this closes

The phase gates used to apply only to file-editing tools. A write against the
platform performed by an MCP server -- creating an item, uploading a file to
storage, modifying a semantic model -- touched no file in the repository and
therefore passed no gate. In practice the phases governed the code and not the
data: you could be in PROFILING, which is read-only by definition, and still
write to the platform.

MCP tools are presented to hooks like any other tool, named
`mcp__<server>__<tool>`, so a matcher reaches them. That is what makes this gate
possible.

## Why the gate lives here and not in the server

Microsoft's own documentation for its Fabric MCP servers warns that an
autonomous or misconfigured client can perform destructive operations, and that
the mechanisms to prevent it are not standardized in the MCP specification. The
design consequence is that the safeguard has to live in the orchestrator.

## Reads and writes are not treated the same

Blocking every MCP tool would break the method instead of reinforcing it:
PROFILING exists to measure the source, and measuring it requires reading it.
The gate classifies by tool name and, when in doubt, treats the call as a write.
Over-classifying a read costs one unnecessary authorization; under-classifying a
write lets it through unchecked.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common  # noqa: E402
import project  # noqa: E402

# Read-only verbs, compared against the tool name with the server prefix removed.
# The list is deliberately conservative: adding a missing read verb costs one
# line, while removing one that actually wrote costs a bad write nobody saw.
READ_VERBS = (
    "list", "get", "read", "search", "describe", "show", "query", "fetch",
    "find", "docs", "inspect", "preview", "count", "check", "validate",
    "download",
)

# Tools that are read-only by design of the server, regardless of their name.
# `execute_query` on the Fabric SQL analytics endpoint queries an endpoint that
# accepts no INSERT, UPDATE or DELETE: the name reads like a write and the
# operation is not one.
EXPLICIT_READS = {
    "execute_query",
    "execute_dax_query",
}

# Tools that run arbitrary code or definitions. However harmless the verb looks,
# what runs inside can write.
EXPLICIT_WRITES = {
    "run_statement",
    "livy_run_statement",
    "execute_sql",
    "apply_migration",
}

# The gate is limited to servers that operate the data platform. A project may
# have a calendar or mail server connected, and stopping those calls because of
# the phase of a data task would be noise with no failure behind it. Compared as
# a substring of the server name.
DATA_SERVERS = ("fabric", "powerbi", "power-bi", "onelake", "synapse",
                "databricks", "sqlendpoint", "sql-endpoint")


def _split(tool: str) -> tuple[str, str] | None:
    """Server and tool from `mcp__<server>__<tool>`."""
    if not tool.startswith("mcp__"):
        return None
    rest = tool[len("mcp__"):]
    if "__" not in rest:
        return None
    server, name = rest.split("__", 1)
    return server, name


def is_read(tool_name: str) -> bool:
    """Classify an MCP tool. When in doubt, it is not a read."""
    n = tool_name.lower()
    if n in EXPLICIT_WRITES:
        return False
    if n in EXPLICIT_READS:
        return True
    first_verb = n.split("_", 1)[0]
    return first_verb in READ_VERBS


def main() -> int:
    common.prepare_output()

    data = common.payload()
    if data is None:
        return 0

    repo = Path(data.get("cwd") or ".")
    if not common.active(repo):
        return 0

    tool = data.get("tool_name") or ""
    parts = _split(tool)
    if parts is None:
        return 0
    server, tool_name = parts

    p = project.profile(repo)
    known = tuple(p["channel"].get("mcp_servers") or ()) + DATA_SERVERS
    if not any(k.lower() in server.lower() for k in known):
        return 0

    if is_read(tool_name):
        return 0

    state = common.read_state(repo)
    phase = common.phase_of(state)

    if not state or phase in (None, "IDLE"):
        return common.deny(
            f"FAW: write to the platform denied. `{tool}` modifies the environment and "
            "there is no classified work open.\n"
            "A write with no open ticket is recorded nowhere: there is no receipt to "
            "attach it to and no phase that justifies it.\n"
            "Classify first (tier and scope, with the user's approval), then register "
            "the work with state.py.\n"
            "If you only need to read, use a query tool: reads need no classification."
        )

    if phase == "CLASSIFICATION":
        return common.deny(
            f"FAW: write to the platform denied. The phase is CLASSIFICATION, which is "
            f"closed by agreeing on scope with the user, not by touching the environment.\n"
            f"`{tool}` writes. Move phase first, with the user's approval recorded as a gate."
        )

    if phase == "PROFILING":
        return common.deny(
            f"FAW: write to the platform denied. The phase is PROFILING, which is "
            f"read-only by definition: the source is measured as it stands, without "
            f"altering it.\n"
            f"`{tool}` writes. If writing is genuinely required in order to profile -- a "
            "temporary table, for instance -- that is the user's decision: raise it and "
            "move phase with their approval."
        )

    if project.requires_written_authorization(p):
        reason = common.consume_override(repo, "tenant-authorization.txt")
        if not reason:
            return common.deny(
                f"FAW: write to the platform denied. `{tool}` writes to {server}, and this "
                "project declares no separate development environment: whatever is written "
                "lands on data someone is using.\n"
                f"{project.write_rule(p)}\n"
                "Write the reason and the operation to .faw/tenant-authorization.txt and "
                "retry. The file is consumed when used, so a one-off authorization does not "
                "become a standing permission.\n"
                "The hook runs BEFORE the command: writing the file and running the tool in "
                "the same call does not work, because the file does not exist yet at that "
                "point."
            )
        print(f"[faw] write to the platform authorized in writing: {reason}", file=sys.stderr)
        return 0

    # There is a development environment: the authorization of the turn remains
    # something the agent states, not something this hook can verify. The rule is
    # restated instead of simulating a check that does not exist.
    print(
        f"[faw] `{tool}` writes to {server}. {project.write_rule(p)} {project.run_record(p)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
