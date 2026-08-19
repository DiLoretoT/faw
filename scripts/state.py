#!/usr/bin/env python3
"""
FAW state machine.

Records and validates transitions between phases. The history lives in
.faw/state.jsonl, append-only: not for formal auditing, but so that when someone
picks the work up two weeks later, the answer to "where were we" does not depend
on anyone's memory.

Usage
-----
  python state.py start --tier ARTIFACT --title "dim_supplier"
  python state.py start --ticket JIRA-12 --tier ARTIFACT --title "dim_supplier"
  python state.py status
  python state.py move --to PROFILING
  python state.py move --to DESIGN --gate profile=docs/faw/T-001/profiling.md
  python state.py pause --reason "waiting for the finance team to confirm"
  python state.py abandon --reason "the requirement changed"

Gates with strength 'machine' are NOT satisfied with --gate: their script has to
run, and this program checks the receipt it left. Gates with strength 'receipt'
require the file to exist. Gates with strength 'declaration' are recorded with
--gate key="text".

Per-table gates (`contract`, `schema`) issue one receipt per table. If the ticket
covers more than one, declare the scope on the move:

  python state.py move --to BUILD --gate tables=gold.dim_a,gold.fact_b

and the gate requires a valid receipt for EVERY declared table. With a single
table nothing needs to be declared.

Exit code: 0 if the transition is valid and was recorded, 1 if it is rejected.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
STATE_DIR = ROOT / ".faw"
LOG = STATE_DIR / "state.jsonl"
FAW = Path(__file__).resolve().parent.parent
TRANSITIONS = FAW / "faw" / "transitions.json"

sys.path.insert(0, str(FAW))
from faw import project as project_mod  # noqa: E402
from faw import receipts  # noqa: E402
from faw import tickets as tickets_mod  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except FileNotFoundError:
        return None


def _is_git_repo() -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "--git-dir"],
                             capture_output=True, text=True)
        return out.returncode == 0
    except FileNotFoundError:
        return False


def _git_clean() -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain"],
                             capture_output=True, text=True)
        return out.returncode == 0 and not out.stdout.strip()
    except FileNotFoundError:
        return False


def load_rules() -> dict:
    if not TRANSITIONS.exists():
        print(f"ERROR: {TRANSITIONS} does not exist", file=sys.stderr)
        sys.exit(2)
    return json.loads(TRANSITIONS.read_text(encoding="utf-8"))


def read_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_entry(entry: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def current() -> dict | None:
    log = read_log()
    return log[-1] if log else None


# Gates whose verifier works on one table at a time. The receipt is issued per
# table and the gate has to require one for EVERY table in the ticket: with a
# single receipt, a nine-table ticket could close the phase having proven only
# the last one.
PER_TABLE_GATES = {"contract", "schema"}


def _verify_per_table(name: str, definition: dict, declared: dict[str, str],
                      failures: list[str]) -> None:
    """Check a per-table gate.

    The expected set is declared by the agent on the move:
    `--gate tables=gold.dim_a,gold.fact_b`. The declaration fixes the scope --
    it is a declaration because the machine cannot know how many tables a ticket
    covers -- while verifying each receipt remains a machine check.

    With no declaration: if exactly one receipt was issued, that one is checked,
    which is the single-table case and the common one. With more than one the
    move is rejected asking for the declaration, because guessing the set would
    reproduce the same gap with a different face.
    """
    suffix = f"  [run: {definition.get('verifies')}]"
    raw = (declared.get("tables") or "").strip()

    if raw:
        tables = [t.strip() for t in raw.split(",") if t.strip()]
        if not tables:
            failures.append(f"{name}: the 'tables' declaration is empty")
            return
        for t in tables:
            ok, reason = receipts.verify(name, scope=t)
            if not ok:
                failures.append(f"{name} [{t}]: {reason}{suffix}")
        return

    issued = receipts.listing(name)
    scopes = sorted(s for s in issued if s is not None)

    if len(scopes) > 1:
        failures.append(
            f"{name}: there are receipts for {len(scopes)} tables ({', '.join(scopes)}) "
            f"and the ticket did not declare which ones it covers. Declare the scope with "
            f"--gate tables=<t1,t2,...> so the gate requires a receipt for EACH one, not "
            f"only for the last table verified")
        return

    if len(scopes) == 1:
        ok, reason = receipts.verify(name, scope=scopes[0])
        if not ok:
            failures.append(f"{name} [{scopes[0]}]: {reason}{suffix}")
        return

    # Legacy: single receipt with no scope, issued by an earlier version.
    ok, reason = receipts.verify(name)
    if not ok:
        failures.append(f"{name}: {reason}{suffix}")


def _belongs_to_ticket(absolute: Path, declared: str, ticket: str) -> bool:
    """Whether a document can be claimed as the receipt of the open ticket.

    It counts if the ticket appears in the path, which is the usual convention,
    or in the text of the document, which covers projects that keep their
    artifacts outside the repository under a different folder structure.
    """
    if ticket in str(declared):
        return True
    try:
        return ticket in absolute.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False


def verify_gates(names: list[str], rules: dict, declared: dict[str, str],
                 ticket: str | None = None) -> tuple[bool, list[str]]:
    definitions = rules.get("gates", {})
    failures: list[str] = []

    for name in names:
        d = definitions.get(name, {})
        strength = d.get("strength", "declaration")

        if strength == "machine":
            if name == "git-clean":
                if not _is_git_repo():
                    print("  note: git-clean passes vacuously, the working folder is "
                          "not a git repository and there is nothing to leave "
                          "uncommitted")
                elif not _git_clean():
                    failures.append("git-clean: there are uncommitted changes")
                continue
            if name == "metadata" and not _is_git_repo():
                print("  note: metadata passes vacuously, the working folder is not a "
                      "git repository and holds no serialized artifacts to protect")
                continue
            if name in PER_TABLE_GATES:
                _verify_per_table(name, d, declared, failures)
                continue
            # The rest require the receipt their verifier issued. These are NOT
            # satisfied with a string: this program recomputes the hash of the
            # inputs and rejects the receipt if any of them changed.
            ok, reason = receipts.verify(name, require_current_commit=(name == "metadata"))
            if not ok:
                failures.append(f"{name}: {reason}  [run: {d.get('verifies')}]")
            continue

        if strength == "receipt":
            # `contract` is issued by its own verifier; the rest are documents
            # whose path the agent declares.
            if name in PER_TABLE_GATES:
                _verify_per_table(name, d, declared, failures)
                continue
            path = declared.get(name)
            if not path:
                failures.append(f"{name}: the receipt path is missing")
            elif not (ROOT / path).exists():
                failures.append(f"{name}: the receipt '{path}' does not exist")
            elif (ROOT / path).stat().st_size < 200:
                failures.append(f"{name}: '{path}' is under 200 bytes. A profiling receipt "
                                f"with no queries in it is not a receipt")
            elif ticket and not _belongs_to_ticket(ROOT / path, path, ticket):
                # Without this link, any file over 200 bytes closes the gate: that
                # the receipt belonged to the work in progress was held together by
                # a naming convention, not by code.
                failures.append(f"{name}: '{path}' does not mention ticket {ticket} in its "
                                f"path or its contents, so it cannot be claimed as the "
                                f"receipt for this work")
            continue

        if name not in declared or not declared[name].strip():
            failures.append(f"{name}: the declaration is missing")

    return (not failures), failures


def cmd_start(a) -> int:
    rules = load_rules()
    tiers = list(rules.get("tiers", {}))
    if a.tier not in tiers:
        print(f"Unknown tier: '{a.tier}'.\nValid tiers: {', '.join(tiers)}", file=sys.stderr)
        return 1

    open_work = current()
    if open_work and open_work.get("phase") != "IDLE":
        print(f"Work is already open: {open_work['ticket']} in {open_work['phase']}.\n"
              f"Close it, pause it or abandon it before starting another.", file=sys.stderr)
        return 1

    p = project_mod.profile(ROOT)
    system = p["tickets"]["system"]

    ticket = a.ticket
    if ticket:
        clean = tickets_mod.sanitize(ticket)
        if not clean:
            print(f"Invalid identifier: '{ticket}'.\n"
                  f"It is used as a directory name (docs/faw/<ticket>/), so it only "
                  f"accepts letters, digits, dot, dash and underscore.", file=sys.stderr)
            return 1
        ticket = clean
    elif system == "internal":
        ticket = tickets_mod.new_identifier(ROOT)
    else:
        print(f"--ticket is missing. This project declares '{system}' as its ticket system "
              f"in {project_mod.CONFIG_FILE}, so the identifier comes from there.\n"
              f"If the work has no ticket in {system}, create it first: work with no "
              f"external record is invisible to the rest of the team.", file=sys.stderr)
        return 1

    if a.context and not (ROOT / a.context).exists():
        # The hook injects this path on every turn so the agent reads it before
        # asking. A path that does not exist sends it to read nothing and leads to
        # asking again what the user already answered, which is exactly what the
        # prior context exists to prevent.
        print(f"The context document '{a.context}' does not exist.\n"
              f"Declare the path of the document produced by the prior consultation, "
              f"relative to the repository root.", file=sys.stderr)
        return 1

    if system == "internal" and not tickets_mod.path_for(ROOT, ticket).exists():
        tickets_mod.create(ROOT, ticket, a.title, a.tier)

    append_entry({"ts": _now(), "event": "start", "ticket": ticket,
                  "tier": a.tier, "title": a.title, "phase": "CLASSIFICATION",
                  "from_phase": "IDLE", "commit": _commit(),
                  "artifact": a.artifact or None,
                  "context": a.context or None,
                  # Records which environment rules the work was opened under.
                  # Without this, changing the profile halfway makes the history
                  # unreadable, because there is no way to tell which regime each
                  # transition happened under.
                  "single_environment": project_mod.single_environment(p)})

    print(f"  {ticket} [{a.tier}] - CLASSIFICATION")
    if system == "internal":
        print(f"  ticket: {tickets_mod.path_for(ROOT, ticket).relative_to(ROOT)}")
    if a.context:
        print(f"  prior context: {a.context}")
    return 0


def cmd_status(a) -> int:
    work = current()
    if not work:
        print("\n  No work recorded.\n")
        return 0
    print(f"\n  Ticket : {work.get('ticket')}")
    print(f"  Tier   : {work.get('tier')}")
    print(f"  Title  : {work.get('title', '-')}")
    print(f"  Phase  : {work.get('phase')}")
    print(f"  Since  : {work.get('ts')}")
    if work.get("reason"):
        print(f"  Reason : {work['reason']}")

    rules = load_rules()
    tier = rules.get("tiers", {}).get(work.get("tier"), {})
    exits = [k for k in tier if k.startswith(f"{work.get('phase')}->")]
    if exits:
        print("\n  Possible exits:")
        for e in exits:
            g = tier[e].get("gates", [])
            print(f"    {e.split('->')[1]:<14} gates: {', '.join(g) or 'none'}")
    print()
    return 0


def _norm_phase(name: str) -> str:
    """Phase names are compared uppercase and trimmed, so that copying one from
    the documentation into `move --to` works regardless of how it was typed."""
    return name.strip().upper()


def cmd_move(a) -> int:
    work = current()
    if not work or work.get("phase") == "IDLE":
        print("No work is open. Start with `start`.", file=sys.stderr)
        return 1

    rules = load_rules()
    origin, destination, tier = work["phase"], _norm_phase(a.to), work["tier"]
    key = f"{origin}->{destination}"

    table = dict(rules.get("common", {}))
    table.update(rules.get("tiers", {}).get(tier, {}))

    if key not in table:
        possible = [k for k in table if k.startswith(f"{origin}->")]
        print(f"Transition not allowed for tier {tier}: {key}\n"
              f"From {origin} you can go to: "
              f"{', '.join(p.split('->')[1] for p in possible) or 'nowhere'}",
              file=sys.stderr)
        return 1

    declared = dict(x.split("=", 1) for x in (a.gate or []) if "=" in x)
    ok, failures = verify_gates(table[key].get("gates", []), rules,
                                declared, work.get("ticket"))
    if not ok:
        print(f"\n  Transition {key} REJECTED:\n", file=sys.stderr)
        for f in failures:
            print(f"    - {f}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    append_entry({"ts": _now(), "event": "move", "ticket": work["ticket"],
                  "tier": tier, "title": work.get("title"), "from_phase": origin,
                  "phase": destination, "gates": declared, "commit": _commit()})
    print(f"  {origin} -> {destination}")
    return 0


def _exit_work(a, event: str) -> int:
    work = current()
    if not work or work.get("phase") == "IDLE":
        print("No work is open.", file=sys.stderr)
        return 1
    rules = load_rules()
    if event == "abandon" and work["phase"] in rules.get("no_abandon", []):
        print(f"{work['phase']} cannot be abandoned. Nothing is left to decide here, "
              f"only steps left to finish. Close with `move --to IDLE`, or pause if "
              f"you are waiting on something.", file=sys.stderr)
        return 1
    append_entry({"ts": _now(), "event": event, "ticket": work["ticket"],
                  "tier": work["tier"], "title": work.get("title"),
                  "from_phase": work["phase"], "phase": "IDLE", "reason": a.reason,
                  "commit": _commit()})
    print(f"  {work['ticket']}: {event} in {work['phase']} - {a.reason}")
    return 0


def cmd_resume(a) -> int:
    """Re-enter the phase the work was paused in.

    There is no list of resumable phases: the proof is the pause itself.
    """
    log = read_log()
    if not log:
        print("There is no history.", file=sys.stderr)
        return 1
    last = log[-1]
    if last.get("event") != "pause":
        print(f"The last recorded event is '{last.get('event')}', not a pause. "
              f"Only paused work can be resumed.", file=sys.stderr)
        return 1
    phase = last.get("from_phase")
    append_entry({"ts": _now(), "event": "resume", "ticket": last["ticket"],
                  "tier": last["tier"], "title": last.get("title"),
                  "from_phase": "IDLE", "phase": phase, "commit": _commit()})
    print(f"  {last['ticket']} resumed in {phase}")
    if last.get("reason"):
        print(f"  it had been paused because: {last['reason']}")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW state machine")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    # Optional on purpose: with the internal registry FAW generates the
    # identifier. Requiring it forced whoever uses no tracker to invent one.
    s.add_argument("--ticket", default="")
    s.add_argument("--tier", required=True)
    s.add_argument("--title", default="")
    # Artifact type: decides which official platform skill applies. Without it the
    # method cannot ask for the right documentation, because it does not know
    # which one that is.
    s.add_argument("--artifact", default="")
    # Document from a prior consultation whose result already closed design
    # decisions. Prevents asking again what the user has already answered.
    s.add_argument("--context", default="")

    sub.add_parser("status")
    sub.add_parser("resume")

    m = sub.add_parser("move")
    m.add_argument("--to", required=True)
    m.add_argument("--gate", action="append", metavar="key=value")

    for name in ("pause", "abandon"):
        x = sub.add_parser(name)
        x.add_argument("--reason", required=True)

    a = p.parse_args()
    return {
        "start": cmd_start, "status": cmd_status, "move": cmd_move,
        "resume": cmd_resume,
        "pause": lambda x: _exit_work(x, "pause"),
        "abandon": lambda x: _exit_work(x, "abandon"),
    }[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
