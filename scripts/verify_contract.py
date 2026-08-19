#!/usr/bin/env python3
"""
The `schema` gate: compares the real schema of a table against its contract.

This is the gate that catches the characteristic failure of a data platform: a
table that has the right number of rows and is missing columns.

Usage
-----
  # Contract syntax only (the `contract` gate, end of DESIGN)
  python verify_contract.py contracts/core.dim_date.yml --syntax-only

  # Real comparison (the `schema` gate, end of VALIDATION)
  python verify_contract.py contracts/core.dim_date.yml --schema schema.json

The schema file is produced by the agent against the tenant. For example:

    import json, datetime
    df = spark.table("core.dim_date")
    print(json.dumps({
        "table": "core.dim_date",
        "measured_at": datetime.datetime.utcnow().isoformat() + "Z",
        "rows": df.count(),
        "columns": [{"name": c.name, "type": c.dataType.simpleString(),
                     "nullable": c.nullable} for c in df.schema.fields],
    }, indent=2))

Being honest about how strong this gate is: the *comparison* is a machine check
and cannot be faked. The *schema snapshot* is a receipt, produced by the agent.
What is gained is that the agent can no longer say "validated" after looking at a
row count: it has to produce the entire schema, and this script confronts it
column by column.

Exit: 0 if it passes, 1 if it fails, 2 if the contract or the snapshot are
malformed.
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


REQUIRED_FIELDS = ["table", "layer", "grain", "natural_key", "columns"]
COLUMN_FIELDS = ["name", "type", "nullable"]

# Accepted synonyms between what is declared and what the engine returns.
EQUIVALENTS = {
    "int": {"int", "integer"},
    "bigint": {"bigint", "long"},
    "string": {"string", "varchar", "str"},
    "double": {"double", "float64"},
    "boolean": {"boolean", "bool"},
    "date": {"date"},
    "timestamp": {"timestamp"},
}


def _normalize(declared_type: str) -> str:
    t = (declared_type or "").strip().lower()
    for canonical, aliases in EQUIVALENTS.items():
        if t in aliases:
            return canonical
    return t  # decimal(18,2) and the like are left as they came


class Result:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

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


def validate_syntax(contract: dict, r: Result) -> None:
    for field in REQUIRED_FIELDS:
        if field not in contract or contract[field] in (None, "", []):
            r.error(f"required field '{field}' is missing")

    grain = contract.get("grain", "")
    if grain and not grain.strip().lower().startswith("one row per"):
        r.warn("the grain does not start with 'one row per'. That form is worth keeping: "
               "it forces the decision to be made explicitly")

    columns = contract.get("columns") or []
    if not isinstance(columns, list):
        r.error("'columns' has to be a list")
        return

    seen: set[str] = set()
    for i, col in enumerate(columns):
        if not isinstance(col, dict):
            r.error(f"column #{i}: has to be a mapping")
            continue
        for field in COLUMN_FIELDS:
            if field not in col:
                r.error(f"column '{col.get('name', f'#{i}')}': '{field}' is missing")
        name = col.get("name")
        if name in seen:
            r.error(f"column '{name}' is declared twice")
        seen.add(name)

    # The natural key has to exist among the declared columns.
    for k in contract.get("natural_key") or []:
        if k not in seen:
            r.error(f"the natural key includes '{k}', which is not among the columns")

    # A nullable natural key is a contradiction.
    by_name = {c.get("name"): c for c in columns if isinstance(c, dict)}
    for k in contract.get("natural_key") or []:
        col = by_name.get(k)
        if col and col.get("nullable") is True:
            r.error(f"'{k}' is part of the natural key and is declared nullable")

    # A uniqueness rule over the natural key ought to exist.
    rules = contract.get("quality") or []
    has_uniqueness = any(x.get("rule") == "uniqueness" for x in rules if isinstance(x, dict))
    if not has_uniqueness:
        r.warn("there is no 'uniqueness' quality rule. Without one, nothing verifies the grain")


def compare_schema(contract: dict, snap: dict, r: Result) -> None:
    contract_table = contract.get("table")
    snap_table = snap.get("table")
    if contract_table != snap_table:
        r.error(f"the snapshot is for '{snap_table}' and the contract for '{contract_table}'")
        return

    if "measured_at" not in snap:
        r.warn("the snapshot does not say when it was measured")

    declared = {c["name"]: c for c in contract["columns"]}
    actual = {c["name"]: c for c in snap.get("columns", [])}

    missing = [n for n in declared if n not in actual]
    extra = [n for n in actual if n not in declared]

    for n in missing:
        r.error(f"column declared and absent from the table: '{n}'")
    for n in extra:
        r.error(f"column in the table and not declared in the contract: '{n}'")

    for n, dec in declared.items():
        real = actual.get(n)
        if not real:
            continue
        t_declared, t_real = _normalize(dec["type"]), _normalize(real["type"])
        if t_declared != t_real:
            r.error(f"'{n}': declared type '{dec['type']}', actual '{real['type']}'")
        # A column declared NOT NULL that the table allows to be null is a real
        # risk: it is exactly how a foreign key ends up null without anyone
        # noticing.
        if dec.get("nullable") is False and real.get("nullable") is True:
            r.warn(f"'{n}': declared not nullable, the table allows nulls "
                   f"(the storage format does not enforce NOT NULL: check it with a "
                   f"quality rule)")

    print(f"  columns declared: {len(declared)}   in the table: {len(actual)}")
    if "rows" in snap:
        print(f"  rows: {snap['rows']}")

    for rule in contract.get("quality") or []:
        if not isinstance(rule, dict):
            continue
        if rule.get("rule") == "rows" and "rows" in snap:
            n = snap["rows"]
            lo, hi = rule.get("min"), rule.get("max")
            if lo is not None and n < lo:
                r.error(f"rows={n}, below the declared minimum ({lo})")
            if hi is not None and n > hi:
                r.error(f"rows={n}, above the declared maximum ({hi})")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW schema gate")
    p.add_argument("contract", type=Path)
    p.add_argument("--schema", type=Path,
                   help="JSON with the real schema measured against the tenant")
    p.add_argument("--syntax-only", action="store_true")
    args = p.parse_args()

    if not args.contract.exists():
        print(f"ERROR: {args.contract} does not exist", file=sys.stderr)
        return 2

    try:
        contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"ERROR: the contract is not valid YAML: {e}", file=sys.stderr)
        return 2

    r = Result()
    validate_syntax(contract, r)

    # The receipt is issued per table (scope): a ticket can touch several, and
    # with a single file each run overwrote the previous one, so the gate closed
    # DESIGN having proven only the last table verified.
    table = contract.get("table") if isinstance(contract, dict) else None

    if args.syntax_only:
        r.report(f"Syntax: {args.contract.name}")
        if r.passed:
            receipts.issue("contract", "verify_contract.py --syntax-only",
                           [args.contract],
                           f"{table}: {len(contract.get('columns') or [])} columns declared, "
                           f"grain and key present",
                           scope=table)
        else:
            receipts.invalidate("contract", scope=table)
        return 0 if r.passed else 1

    if not args.schema:
        print("ERROR: --schema is required, or --syntax-only.\n"
              "       Without the real schema there is nothing to compare, and a gate\n"
              "       that skips itself when its input is missing is not a gate.",
              file=sys.stderr)
        return 2

    if not args.schema.exists():
        print(f"ERROR: {args.schema} does not exist", file=sys.stderr)
        return 2

    try:
        snap = json.loads(args.schema.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: the snapshot is not valid JSON: {e}", file=sys.stderr)
        return 2

    if r.passed:
        compare_schema(contract, snap, r)

    r.report(f"Schema: {contract.get('table')}")
    if r.passed:
        receipts.issue("schema", "verify_contract.py",
                       [args.contract, args.schema],
                       f"{contract.get('table')}: {len(contract['columns'])} columns match, "
                       f"{snap.get('rows', '?')} rows",
                       scope=table)
    else:
        receipts.invalidate("schema", scope=table)
    return 0 if r.passed else 1


if __name__ == "__main__":
    sys.exit(main())
