#!/usr/bin/env python3
"""
The `report` gate.

The silent failure of the reporting layer is the development filter left behind
("only client X to test this", "only 2025") and persisted in the report file. It
publishes numbers that are credible and filtered. It is the exact equivalent of
the null foreign key: invisible in the view you would use to check it, because
nobody opens the filter definition before publishing.

This script does TWO things of different strength, on purpose:

1. **Dump of persisted filters** (a receipt: a human reviews it). It walks every
   JSON file of the report project looking for any "filters" key, without
   assuming a particular version of the schema. That is deliberately
   format-agnostic: the report definition format is relatively new, and there is
   no verified reading of its complete specification behind this script. Before
   relying on it for a real case, check it against the current documentation, as
   principle 6 requires.

2. **Fields referenced per visual, against the model** (a heuristic, first
   iteration). It looks for field-reference patterns in the JSON files and cross
   checks them against the tables, columns and measures of the model definition.
   This needs tuning against a real project the first time it is used in earnest,
   and it is declared as a heuristic rather than as guaranteed verification.

Usage
-----
  python verify_report.py --report "<report name>"       --definition MyReport.Report --model model.bim.json

Exit: 0 if it finds no unreviewed orphan fields, 1 if there is something for a
human to look at, 2 if the inputs are wrong.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import project, receipts  # noqa: E402


def _find_filters(node, file_path: str, found: list[dict], trail: str = "") -> None:
    """Walk any JSON structure looking for filter keys, without assuming a schema."""
    if isinstance(node, dict):
        for key, value in node.items():
            new_trail = f"{trail}.{key}" if trail else key
            if key.lower() == "filters" and value:
                found.append({"file": file_path, "at": new_trail, "value": value})
            else:
                _find_filters(value, file_path, found, new_trail)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _find_filters(item, file_path, found, f"{trail}[{i}]")


def _find_fields(node, found: set[str]) -> None:
    """Heuristic: collect values of the keys that typically reference a field."""
    if isinstance(node, dict):
        for key in ("Column", "Measure", "Property", "Hierarchy"):
            if key in node and isinstance(node[key], str):
                found.add(node[key])
        for v in node.values():
            _find_fields(v, found)
    elif isinstance(node, list):
        for item in node:
            _find_fields(item, found)


RE_LAYOUT_PAGE = re.compile(r"^###\s+(?:\d+[\.\)]\s*)?(.+)$", re.MULTILINE)


def _declared_pages(layout: Path) -> list[str]:
    """Page names from the layout agreement, in declaration order."""
    text = layout.read_text(encoding="utf-8", errors="replace")
    return [m.strip() for m in RE_LAYOUT_PAGE.findall(text) if m.strip()]


def _built_pages(report: Path) -> list[str]:
    """Page names found in the report project.

    Read from the folder structure rather than from one schema field, because the
    shape of the definition changes between versions and the folders do not. A
    page whose display name cannot be read falls back to its folder name instead
    of being skipped: dropping it silently would make the comparison claim more
    than it knows.
    """
    pages_dir = next((d for d in report.rglob("pages") if d.is_dir()), None)
    if pages_dir is None:
        return []
    names = []
    for child in sorted(d for d in pages_dir.iterdir() if d.is_dir()):
        display = None
        for candidate in child.glob("*.json"):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, dict) and data.get("displayName"):
                display = str(data["displayName"])
                break
        names.append(display or child.name)
    return names


def _compare_layout(report: Path, layout: Path) -> list[str]:
    """Built pages against agreed pages. Returns the findings.

    This is what turns the layout agreement from a plan into a contract. Checked
    only on the way into BUILD, the agreement is read once and never again, so a
    report that drifts from what was agreed publishes with nothing noticing.
    """
    declared = _declared_pages(layout)
    built = _built_pages(report)
    findings = []

    if not declared:
        findings.append(f"the layout agreement at {layout} declares no page")
        return findings
    if not built:
        findings.append(f"no page found under {report}, so it cannot be compared "
                        f"against the {len(declared)} agreed")
        return findings

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    built_norm = {norm(b): b for b in built}
    declared_norm = {norm(d): d for d in declared}

    for key, name in declared_norm.items():
        if key not in built_norm:
            findings.append(f"page agreed and not built: '{name}'")
    for key, name in built_norm.items():
        if key not in declared_norm:
            findings.append(f"page built and not agreed: '{name}'. Either it answers a "
                            f"question the agreement missed, or nobody asked for it")
    return findings


def model_fields(model: dict) -> set[str]:
    m = model.get("model", model)
    fields: set[str] = set()
    for t in m.get("tables", []):
        for c in t.get("columns", []):
            fields.add(c["name"])
        for med in t.get("measures", []):
            fields.add(med["name"])
    return fields


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW report gate")
    p.add_argument("--report", required=True,
                   help="report name; resolves its layout agreement under "
                        "docs/faw/reports/<report>/layout.md")
    p.add_argument("--definition", type=Path, required=True,
                   help="report project folder (.Report), the artifact that was built")
    p.add_argument("--model", type=Path, required=True, help="model definition (JSON)")
    p.add_argument("--layout", type=Path,
                   help="explicit path to the layout agreement, overriding the one "
                        "resolved from --report")
    args = p.parse_args()

    if not args.definition.exists() or not args.definition.is_dir():
        print(f"ERROR: the folder {args.definition} does not exist", file=sys.stderr)
        return 2
    if not args.model.exists():
        print(f"ERROR: {args.model} does not exist", file=sys.stderr)
        return 2

    try:
        model = json.loads(args.model.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: malformed model: {e}", file=sys.stderr)
        return 2

    json_files = list(args.definition.rglob("*.json"))
    if not json_files:
        print(f"ERROR: no .json file found under {args.definition}", file=sys.stderr)
        return 2

    filters: list[dict] = []
    used_fields: set[str] = set()
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # some project files are not content JSON
        rel = str(jf.relative_to(args.definition)).replace("\\", "/")
        _find_filters(data, rel, filters)
        _find_fields(data, used_fields)

    available = model_fields(model)
    orphans = sorted(c for c in used_fields if c not in available)

    print(f"\n=== Report: {args.report} ===")
    print(f"  JSON files inspected: {len(json_files)}")
    print(f"  fields and measures referenced (heuristic): {len(used_fields)}")

    layout_findings: list[str] = []
    layout_path = None
    if args.layout:
        layout_path = (args.layout if args.layout.is_absolute()
                       else (project.root() or Path.cwd()) / args.layout)
    else:
        resolved = project.report_dir(args.report) / "layout.md"
        if resolved.exists():
            layout_path = resolved
    if layout_path is not None:
        if not layout_path.exists():
            print(f"ERROR: {layout_path} does not exist", file=sys.stderr)
            return 2
        layout_findings = _compare_layout(args.definition, layout_path)
        print(f"  pages agreed: {len(_declared_pages(layout_path))}   "
              f"built: {len(_built_pages(args.definition))}")

    has_problem = bool(layout_findings)

    if layout_findings:
        print("\n  [ERROR] the report does not match the layout agreement:")
        for f in layout_findings:
            print(f"      {f}")

    if orphans:
        has_problem = True
        print(f"\n  [ERROR] {len(orphans)} references that are NOT in the model "
              f"(check whether they are typos, renamed fields, or false positives of "
              f"the heuristic):")
        for h in orphans[:20]:
            print(f"      {h}")
        if len(orphans) > 20:
            print(f"      ... and {len(orphans) - 20} more")

    if filters:
        print(f"\n  [WARNING] {len(filters)} persisted filters found. Check that none of "
              f"them is a forgotten development filter:")
        for f in filters[:15]:
            summary = json.dumps(f["value"])[:150]
            print(f"      {f['file']}  ({f['at']})")
            print(f"          {summary}")
        if len(filters) > 15:
            print(f"      ... and {len(filters) - 15} more")
        # Filters are a receipt for human review; they do not fail on their own.
    else:
        print("\n  persisted filters: none found")

    passed = not has_problem
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")

    detail = (f"{len(json_files)} files, {len(used_fields)} fields referenced, "
              f"{len(orphans)} orphans, {len(filters)} filters to review")
    # The definition files are inputs of the receipt, not only the model. With
    # the model alone, a page edited after the gate passed left the receipt valid
    # and the report published without being checked again -- which is the same
    # drift the layout comparison exists to catch, moved one step later.
    inputs = [args.model, *sorted(json_files)]
    if layout_path is not None:
        detail += ", pages match the layout agreement"
        inputs.append(layout_path)
    if passed:
        receipts.issue("report", "verify_report.py", inputs, detail)
    else:
        receipts.invalidate("report")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
