#!/usr/bin/env python3
"""
The `model` gate: compares the real definition of a semantic model against what
was declared.

The "new relationship" dialog comes with a column preselected, and accepting it
without looking leaves relationships for different date roles -- or any other
repeated role -- pointing at the same column of the fact table. The result
filters by the wrong role with no error and no warning: totals that are plausible
and wrong.

The model diagram draws a line between two tables; it does not show which column
it lands on. The mistake is invisible in the very view you would look at to check
it. That is why this is verified by reading the definition rather than by looking
at the screen.

Usage
-----
  python verify_model.py model.expected.yml --definition model.bim.json

The definition is obtained from the platform tooling in TMSL format and decoding
the payload of the model definition part.

Exit: 0 if it passes, 1 if it fails, 2 if a file is malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is missing.  pip install pyyaml", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import receipts  # noqa: E402


# Query connector by Direct Lake flavor. Used to verify that the model came out
# in the mode that was decided and not in the default of whichever button was
# pressed.
CONNECTOR_BY_MODE = {
    "directlake_onelake": "AzureStorage.DataLake",
    "directlake_sql": "Sql.Database",
}


class Result:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, m: str) -> None:
        self.errors.append(m)

    def warn(self, m: str) -> None:
        self.warnings.append(m)

    @property
    def passed(self) -> bool:
        return not self.errors

    def report(self, title: str) -> None:
        print(f"\n=== {title} ===")
        for w in self.warnings:
            print(f"  [warning] {w}")
        for e in self.errors:
            print(f"  [ERROR] {e}")
        print(f"\n  {'PASS' if self.passed else 'FAIL'}"
              f"  ({len(self.errors)} errors, {len(self.warnings)} warnings)\n")


def _rel_str(r: dict) -> str:
    return (f"{r.get('fromTable')}[{r.get('fromColumn')}] -> "
            f"{r.get('toTable')}[{r.get('toColumn')}]")


def check(expected: dict, model: dict, r: Result) -> None:
    m = model.get("model", model)
    tables = {t["name"]: t for t in m.get("tables", [])}

    # --- Tables ---
    expected_tables = set(expected.get("tables") or [])
    actual_tables = set(tables)
    for t in sorted(expected_tables - actual_tables):
        r.error(f"table declared and absent from the model: '{t}'")
    for t in sorted(actual_tables - expected_tables):
        r.error(f"table in the model and not declared: '{t}'")
    print(f"  tables: {len(actual_tables)}")

    # --- Storage mode ---
    mode = (expected.get("mode") or "").strip().lower()
    if mode in CONNECTOR_BY_MODE:
        wanted = CONNECTOR_BY_MODE[mode]
        expressions = json.dumps(m.get("expressions", []))
        if wanted not in expressions:
            others = [c for k, c in CONNECTOR_BY_MODE.items() if k != mode]
            found = next((c for c in others if c in expressions), "none known")
            r.error(f"declared mode '{mode}' (connector {wanted}), "
                    f"but the model shows: {found}")
        else:
            print(f"  mode: {mode} (connector {wanted}) OK")

    # --- Relationships: the part that matters ---
    actual_rels = m.get("relationships", []) or []
    print(f"  relationships: {len(actual_rels)}")

    pending = list(actual_rels)
    for e in expected.get("relationships") or []:
        match = None
        for candidate in pending:
            if (candidate.get("fromTable") == e["from_table"]
                    and candidate.get("fromColumn") == e["from_column"]
                    and candidate.get("toTable") == e["to_table"]
                    and candidate.get("toColumn") == e["to_column"]):
                match = candidate
                break
        if not match:
            r.error("relationship declared and absent: "
                    f"{e['from_table']}[{e['from_column']}] -> "
                    f"{e['to_table']}[{e['to_column']}]")
            continue
        pending.remove(match)

        # isActive missing in TMSL means active.
        active = match.get("isActive", True)
        if e.get("active", True) != active:
            r.error(f"{_rel_str(match)}: active={active}, "
                    f"declared active={e.get('active', True)}")

    for extra in pending:
        r.error(f"relationship in the model and not declared: {_rel_str(extra)}")

    # Two different relationships pointing at the same target column is the exact
    # pattern this verifier exists to catch. It can be legitimate, but it should
    # never happen without someone having looked at it.
    targets: dict[str, list[str]] = {}
    for rel in actual_rels:
        key = f"{rel.get('toTable')}[{rel.get('toColumn')}]"
        targets.setdefault(key, []).append(_rel_str(rel))
    for key, group in targets.items():
        if len(group) > 1:
            r.warn(f"{len(group)} relationships point at {key}. Check that this is not "
                   f"the column the dialog preselected:\n"
                   + "".join(f"           {x}\n" for x in group))

    # --- Column properties ---
    for pc in expected.get("columns") or []:
        t = tables.get(pc["table"])
        if not t:
            continue
        col = next((c for c in t.get("columns", []) if c["name"] == pc["column"]), None)
        if not col:
            r.error(f"{pc['table']}[{pc['column']}]: does not exist in the model")
            continue
        if "summarize" in pc:
            real = col.get("summarizeBy", "default")
            if real != pc["summarize"]:
                r.error(f"{pc['table']}[{pc['column']}]: summarizeBy='{real}', "
                        f"declared '{pc['summarize']}'")
        if "sort_by" in pc:
            real = col.get("sortByColumn")
            if real != pc["sort_by"]:
                r.error(f"{pc['table']}[{pc['column']}]: sortByColumn='{real}', "
                        f"declared '{pc['sort_by']}'")

    # --- Measures ---
    expected_measures = set(expected.get("measures") or [])
    if expected_measures:
        actual_measures = {med["name"] for t in tables.values() for med in t.get("measures", [])}
        for x in sorted(expected_measures - actual_measures):
            r.error(f"measure declared and absent: '{x}'")
        print(f"  measures: {len(actual_measures)}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW semantic model gate")
    p.add_argument("expected", type=Path, help="YAML with what was declared in DESIGN")
    p.add_argument("--definition", type=Path, required=True,
                   help="decoded model definition (JSON)")
    args = p.parse_args()

    for f in (args.expected, args.definition):
        if not f.exists():
            print(f"ERROR: {f} does not exist", file=sys.stderr)
            return 2

    try:
        expected = yaml.safe_load(args.expected.read_text(encoding="utf-8"))
        model = json.loads(args.definition.read_text(encoding="utf-8"))
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        print(f"ERROR: malformed file: {e}", file=sys.stderr)
        return 2

    r = Result()
    check(expected, model, r)
    r.report(f"Model: {expected.get('model', args.expected.stem)}")
    if r.passed:
        receipts.issue("model", "verify_model.py",
                       [args.expected, args.definition],
                       f"{expected.get('model')}: "
                       f"{len(expected.get('relationships') or [])} relationships and "
                       f"mode '{expected.get('mode')}' verified")
    else:
        receipts.invalidate("model")
    return 0 if r.passed else 1


if __name__ == "__main__":
    sys.exit(main())
