#!/usr/bin/env python3
"""
UserPromptSubmit hook: puts the method in front of the model on EVERY turn,
without depending on the agent remembering to go and read it.

Why this event and not SessionStart: UserPromptSubmit runs before Claude
processes each message, so the state is still present after a context
compaction and after `/clear`. SessionStart runs once, which does not cover
re-entering after either of those, and that is exactly where the method can be
written down without the agent knowing it exists.

DESIGN RULE: the injection has to be SHORT. It runs on every turn, and anything
that narrates on every turn trains the reader to skip it. What goes in is the
state, the rule for the current phase, and what changes what the agent may do
without asking.

That rule has a price attached. Claude Code appends this text to every message
and keeps it in the transcript, so a word added here is resent on every turn for
the rest of the session, in every session, for everyone. The block measures
between 80 and 156 tokens depending on tier and phase; treat the upper end as
the ceiling and cut prose before adding any. There is an upstream issue asking
for this context to be ephemeral, which would remove the accumulation but not
the per-turn cost.

Opt-in: it does nothing unless the project has a `.faw/` directory. Installing
the plugin globally does not push data-platform context into unrelated projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import project  # noqa: E402

FAW_ROOT = Path(__file__).resolve().parent.parent.parent
TRANSITIONS = FAW_ROOT / "faw" / "transitions.json"

# No emoji on purpose: on Windows stdout defaults to cp1252 and a character
# outside that set crashes the hook. A hook that crashes exits non-zero, which is
# treated as NON-blocking, so FAW would be installed and enforcing nothing.
# stdout is reconfigured to UTF-8 below anyway, because the ticket title comes
# from the state and may carry accents.
#
# Two constants rather than one because the alternatives are mutually exclusive:
# with work open the `[question]` form cannot apply, and with nothing open the
# form with a ticket cannot. Sending both spent tokens on the branch that was
# never going to be used.
STATE_LINE_OPEN = "Start every reply with `{TIER} - {action} | {ticket}: {title}`."
STATE_LINE_IDLE = "Start every reply with `[question]`."

# What the agent is asked to do about platform tooling. Note what this does NOT
# do: it does not name a skill, a path or a plugin. Any such list would be a
# snapshot of what existed the day it was written, and the vendor reorganizes,
# renames and retires those skills between releases. A stale list is worse than
# no list, because it sends the agent to read something that is gone and looks
# authoritative while doing it.
#
# What holds over time is the obligation itself: look at what is actually
# available in this session, and state which tool was used or why none applied.
# That produces a record instead of an assumption, and it stays true regardless
# of how the vendor reorganizes its catalog.
PLATFORM_TOOLING = (
    "Check which official platform tools this session actually has, state which you "
    "used or why none applied, and do not assume the catalog from memory."
)

# Where a tier needs a different rule for the same phase. Consulted before
# RULE_BY_PHASE, which stays the default.
RULE_BY_TIER_PHASE = {
    ("REPORT", "PROFILING"):
        "Read-only, over the model the report will consume. Grain of each table, "
        "measures that exist, cardinality of what will slice, business totals to "
        "reproduce. Every number with its query. If the model cannot be queried from "
        "here, hand the queries to the user rather than estimating.",
    ("REPORT", "DESIGN"):
        "Read the profiling through the business first, then turn it into a layout. "
        "Every page states which brief question it answers. Closes with the user "
        "agreeing the pages before any get built.",
}

RULE_BY_PHASE = {
    "CLASSIFICATION": "Restate the request, look at the real state, assign a tier, define "
                      "what is NOT included. Build nothing yet. Closes with the user's "
                      "approval.",
    "PROFILING": "Read-only. Every number comes with the query that produced it. The "
                 "natural key is proven, not copied from a spec.",
    "DESIGN": "Grain in one sentence, natural key verified, contract file. Raise the "
              "architecture decisions this work would settle even unasked, because a "
              "default nobody discussed is the tool deciding. Closes with the user's "
              "approval BEFORE building.",
    "BUILD": "Validations go inside the artifact, not in a separate script. Report rows "
             "AND columns.",
    "EXECUTION": "Run only what was scoped. Before each write state table, operation and "
                 "expected delta; after it compare the real one. Success with zero rows "
                 "affected is a failure, not a quiet success.",
    "VALIDATION": "Run by faw-validator, which did not build. It looks to refute, not to "
                  "confirm. A failure returns the work to BUILD and is not patched here.",
    "PUBLICATION": "Check the COMPLETE diff. Read rules/client-surface.md before writing the "
                   "pull request. Update the tracker with the resume point.",
}


def _state(repo: Path) -> dict | None:
    """Current state of the open work, or None if there is none.

    The file is an event log: the current phase is on the last line, but what was
    declared when the work was opened -- the artifact type, the prior-context
    document -- is only on the `start` line. Reading only the last entry would
    make those values exist during the first phase and disappear as soon as work
    advanced, which is worse than not having them: they are declared once and
    silently stop applying.

    So the last entry is combined with the `start` entry of the same ticket,
    instead of requiring every transition to carry all the fields forward.
    """
    f = repo / ".faw" / "state.jsonl"
    if not f.exists():
        return None

    entries = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not entries:
        return None

    last = entries[-1]
    ticket = last.get("ticket")
    for e in reversed(entries):
        if e.get("event") == "start" and e.get("ticket") == ticket:
            combined = dict(e)
            combined.update({k: v for k, v in last.items() if v is not None})
            return combined
    return last


def _exits(tier: str, phase: str) -> str:
    """Legal transitions from where we are, with their gates."""
    try:
        g = json.loads(TRANSITIONS.read_text(encoding="utf-8"))
    except Exception:
        return ""
    edges = (g.get("tiers", {}).get(tier) or {})
    parts = []
    for edge, cfg in edges.items():
        if not isinstance(cfg, dict) or "->" not in edge:
            continue
        origin, destination = edge.split("->", 1)
        if origin != phase:
            continue
        gates = cfg.get("gates") or []
        parts.append(f"{destination}" + (f" (gates: {', '.join(gates)})" if gates else ""))
    return " | ".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0  # nothing readable to inject; fail open

    repo = project.root(data.get("cwd"))
    if repo is None:
        return 0

    st = _state(repo)
    phase = (st or {}).get("phase")
    tier = (st or {}).get("tier")
    ticket = (st or {}).get("ticket")
    title = (st or {}).get("title") or ""

    lines = []

    if not st or phase in (None, "IDLE"):
        lines += [
            "[FAW] No classified work.",
            "Nothing can be edited until classification closes. Assign a tier, define what "
            "is in and what is NOT, wait for the user's approval. The skill is "
            "/faw:classify.",
            f"Register with: python {FAW_ROOT / 'scripts' / 'state.py'} start --tier <TIER> "
            f"--title \"<title>\"",
            STATE_LINE_IDLE,
        ]
    else:
        lines.append(f"[FAW] {tier} - {phase} | {ticket}: {title}")
        # The rule depends on the tier as well as the phase. DESIGN of a report
        # is not DESIGN of a table, and injecting "grain in one sentence, natural
        # key verified" at someone laying out pages would win over the skill:
        # what arrives every turn outweighs what is read once.
        rule = RULE_BY_TIER_PHASE.get((tier or "", phase or "")) or RULE_BY_PHASE.get(phase)
        if rule:
            lines.append(f"Phase {phase}: {rule}")

        # A prior-consultation document already holds decisions closed with the
        # user. The path is named and the content is not dumped: the point is
        # that the agent reads it instead of asking again what was answered.
        prior_context = (st or {}).get("context")
        if prior_context:
            lines.append(f"Decisions already agreed with the user are in {prior_context}. "
                         f"Read it before asking anything that may be there.")

        if phase in ("DESIGN", "BUILD"):
            lines.append(PLATFORM_TOOLING)

        exits = _exits(tier or "", phase)
        if exits:
            lines.append(f"Legal exits: {exits}")
        # The skills say `python <faw>/scripts/state.py` and nothing resolves
        # <faw> until a denial prints it. One line closes that gap.
        lines.append(f"FAW scripts: {FAW_ROOT / 'scripts'}")
        lines.append(STATE_LINE_OPEN)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(lines),
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
