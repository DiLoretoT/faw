"""
Gate receipts.

The problem this solves: an early version of FAW advertised four "machine" gates
and only one of them was. The state machine accepted the agent writing
`--gate schema="ok: ..."` without having run anything. Verified by trying it.

Now a verifier that passes writes a receipt recording WHAT was checked, over
WHICH files (by hash), and at WHICH commit. The state machine requires the
receipt and **recomputes the hashes**: if the contract or the snapshot changed
after it was issued, the receipt is stale and the gate closes.

## How far this goes, stated plainly

A receipt raises the cost of faking from "write a string" to "build a JSON file
with the right hashes, on purpose". That removes the accidental bypass and turns
the deliberate one into an explicit, traceable act. **It does not make it
impossible**: without a secret the agent cannot read, no local file is
unforgeable.

Real irreversibility comes from the hooks, which run outside the conversation.
This is the honest intermediate step, and it is documented as such rather than
promising again what it does not deliver.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import project  # noqa: E402


def _root() -> Path:
    """The governed folder, or the current directory when there is none.

    Resolved rather than assumed: a verifier run from a subdirectory used to
    write its receipt into a `.faw` that the state machine never reads, so the
    gate stayed closed with the receipt sitting one level down.
    """
    return project.root() or Path.cwd()


def _receipts_dir() -> Path:
    return _root() / ".faw" / "receipts"


def _open_ticket() -> str | None:
    """Identifier of the work currently open, or None if there is none.

    Read here rather than passed in by every verifier: the verifiers are
    standalone scripts that do not know the state machine, and threading the
    ticket through all of them would leave the one that forgets it silently
    issuing an unscoped receipt.
    """
    log = _root() / ".faw" / "state.jsonl"
    if not log.exists():
        return None
    last = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    if not last or last.get("phase") in (None, "IDLE"):
        return None
    return last.get("ticket")


def _path(gate: str, scope: str | None = None) -> Path:
    """One receipt per gate, or per (gate, scope) when the verifier works on one
    unit at a time and the ticket spans several.

    The case that made scope necessary: `contract` is checked table by table, and
    with a single file each run overwrote the previous one, so a ticket covering
    nine tables could close DESIGN having proven only the last.
    """
    if scope:
        safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", scope)
        return _receipts_dir() / f"{gate}.{safe}.json"
    return _receipts_dir() / f"{gate}.json"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def _commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except FileNotFoundError:
        return None


def issue(gate: str, script: str, inputs: list[Path], detail: str,
          scope: str | None = None) -> Path:
    """Write the receipt of a gate that passed. Called only by the verifiers."""
    _receipts_dir().mkdir(parents=True, exist_ok=True)
    receipt = {
        "gate": gate,
        "result": "PASS",
        "script": script,
        "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        # Which work this receipt belongs to. Without it a receipt outlives the
        # ticket that produced it and satisfies the gate of the next one: a
        # closed ticket's brief let the following ticket enter BUILD with no
        # brief of its own, because the file still existed and its hash still
        # matched. Recorded at issue time so the check can be a comparison
        # rather than a guess.
        "ticket": _open_ticket(),
        "inputs": {str(p).replace("\\", "/"): _sha(p) for p in inputs if p.exists()},
        "detail": detail,
    }
    if scope:
        receipt["scope"] = scope
    target = _path(gate, scope)
    target.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  receipt: {target}")
    return target


def verify(gate: str, require_current_commit: bool = False,
           scope: str | None = None,
           ticket: str | None = None) -> tuple[bool, str]:
    """Validate the receipt of a gate. Returns (passed, reason).

    Recomputes the hash of every input: if any of them changed after the receipt
    was issued, it is stale. This is what prevents profiling once and then
    changing the contract without checking again.

    When a ticket is given, the receipt has to belong to it. A receipt is
    evidence that a specific piece of work was checked, and one that survives
    its ticket stops being evidence of anything.
    """
    path = _path(gate, scope)
    if not path.exists():
        what = f"'{gate}'" + (f" for '{scope}'" if scope else "")
        return False, f"no receipt for {what}. Run the verifier and try again"

    try:
        r = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, f"the receipt '{path}' is not valid JSON"

    if r.get("result") != "PASS":
        return False, f"the receipt reads result='{r.get('result')}'"

    if scope and r.get("scope") != scope:
        return False, (f"the receipt in '{path.name}' declares scope "
                       f"'{r.get('scope')}', not '{scope}'")

    if ticket:
        owner = r.get("ticket")
        if owner is None:
            return False, (f"the receipt in '{path.name}' does not say which ticket it "
                           f"belongs to, so it cannot be claimed by {ticket}. Run the "
                           f"verifier again with the work open")
        if owner != ticket:
            return False, (f"the receipt in '{path.name}' belongs to ticket {owner}, not "
                           f"{ticket}. Run the verifier for this work")

    for file_name, recorded_hash in (r.get("inputs") or {}).items():
        # Inputs are recorded relative to the governed folder, so they resolve
        # against it rather than against wherever the shell happens to stand.
        p = Path(file_name)
        if not p.is_absolute():
            p = _root() / file_name
        if not p.exists():
            return False, f"stale receipt: the input '{file_name}' no longer exists"
        if _sha(p) != recorded_hash:
            return False, (f"stale receipt: '{file_name}' changed after it was issued. "
                           f"Run the verifier again")

    if require_current_commit:
        current = _commit()
        if current and r.get("commit") and r["commit"] != current:
            return False, (f"receipt issued at commit {r['commit']} while HEAD is at "
                           f"{current}. Verify again")

    detail = r.get("detail", "")
    return True, f"receipt from {r.get('issued_at')} - {detail}"


def invalidate(gate: str, scope: str | None = None) -> None:
    """Delete the receipt. Called by the verifiers when the result is a failure."""
    path = _path(gate, scope)
    if path.exists():
        path.unlink()
        print(f"  receipt invalidated: {path}")


def listing(gate: str) -> dict[str | None, Path]:
    """Issued receipts for a gate, keyed by scope.

    The None key is the legacy receipt with no scope, from the format that
    predates per-table receipts.

    The scope is read from the contents of the receipt and not from the file
    name, because the name sanitizes characters and is not reversible.
    """
    found: dict[str | None, Path] = {}
    if not _receipts_dir().is_dir():
        return found
    legacy = _receipts_dir() / f"{gate}.json"
    if legacy.exists():
        found[None] = legacy
    for p in _receipts_dir().glob(f"{gate}.*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if r.get("gate") == gate and r.get("scope"):
            found[r["scope"]] = p
    return found
