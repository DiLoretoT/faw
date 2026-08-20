#!/usr/bin/env python3
"""
Self-check of the FAW gates: a canary over the verifiers themselves.

Why it exists
-------------
The gates of `state.py` are only as trustworthy as the scripts that implement
them. Nothing guarantees they keep detecting what they claim to detect over
time: an accidental change to a regular expression, an inverted condition, or a
field that stops being read can leave a verifier permanently green without
anyone noticing until something fails in production.

This script does not replace human review or exhaustive testing. For each
verifier it builds, in a temporary directory and never inside the repository, an
input that SHOULD pass and an input with one known, deliberate defect that SHOULD
make it fail: a schema column that does not match the contract, a diff that does
touch protected metadata, a model relationship that is missing, a report field
that does not exist in the model. If the "should fail" case actually passes, or
the "should pass" case actually fails, that verifier has a hole and this script
exits non-zero.

The idea comes from the sibling project DAW, which solves an analogous problem
with real mutation testing: it injects code mutations into its own scripts and
runs the full verification against each mutated copy. That is more thorough and
strongly coupled to infrastructure FAW does not have, so porting it as-is would
not be proportionate. What is adopted here is the underlying idea that DAW states
explicitly -- mutation testing is the gauge, not the detector: it confirms that a
known gate still works, rather than discovering new faults -- expressed as one
good/bad input pair per verifier instead of as code mutation.

Usage
-----
    python scripts/self_check.py

Exit 0 if every case behaved as expected. Exit 1 if any did not. Besides the
individual verifiers there is an end-to-end case against `state.py`, covering the
`contract` gate with several tables, because the gap that motivated that case was
in the gate and not in the verifier.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
PY = sys.executable


def _run(script: str, args: list[str], cwd: Path) -> int:
    r = subprocess.run(
        [PY, str(SCRIPTS_DIR / script), *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.returncode


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                   text=True, check=True)


HOOKS_DIR = SCRIPTS_DIR.parent / "faw" / "hooks"


def _hook(name: str, payload: dict) -> str:
    """Run a hook the way Claude Code does, with the payload on stdin.

    Hooks answer on stdout and always exit 0, so what is asserted here is the
    content of the answer and not the exit code.
    """
    r = subprocess.run(
        [PY, str(HOOKS_DIR / name)],
        input=json.dumps(payload), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.stdout.strip()


# ── Fixtures ──────────────────────────────────────────────────────────────

CONTRATO_YML = """\
table: core.dim_fecha
layer: gold
grain: "one row per fecha"
natural_key:
  - fecha_id
columns:
  - name: fecha_id
    type: int
    nullable: false
  - name: fecha
    type: date
    nullable: false
quality:
  - rule: uniqueness
    columns: [fecha_id]
"""

ESQUEMA_OK = {
    "table": "core.dim_fecha",
    "measured_at": "2026-08-03T00:00:00Z",
    "rows": 100,
    "columns": [
        {"name": "fecha_id", "type": "int", "nullable": False},
        {"name": "fecha", "type": "date", "nullable": False},
    ],
}

# Known defect: the 'date' column is missing. This is the case the schema gate
# exists to catch: correct row count, absent column.
ESQUEMA_FALTA_COLUMNA = {
    "table": "core.dim_fecha",
    "measured_at": "2026-08-03T00:00:00Z",
    "rows": 100,
    "columns": [
        {"name": "fecha_id", "type": "int", "nullable": False},
    ],
}

NOTEBOOK_BASE = """\
{
  "cells": [
    {
      "cell_type": "code",
      "source": ["print('hola mundo')\\n"]
    }
  ],
  "metadata": {
    "default_lakehouse": "lh-bronze-0001",
    "default_lakehouse_name": "LH_Bronze",
    "language_info": {
      "name": "python"
    }
  }
}
"""

# Cosmetic change: only the cell text. It should not trip the gate.
NOTEBOOK_CAMBIO_COSMETICO = NOTEBOOK_BASE.replace("hola mundo", "chau mundo")

# Known defect: it changes default_lakehouse, which is what leaves a notebook
# unable to run and what this gate has to catch.
NOTEBOOK_CAMBIO_METADATA = NOTEBOOK_BASE.replace("lh-bronze-0001", "lh-bronze-9999")

MODEL_ESPERADO_YML = """\
model: ventas
tables:
  - fact_ventas
  - dim_fecha
mode: directlake_onelake
relationships:
  - from_table: fact_ventas
    from_column: fecha_id
    to_table: dim_fecha
    to_column: fecha_id
    active: true
measures:
  - total_ventas
"""

MODEL_BIM_OK = {
    "model": {
        "tables": [
            {"name": "fact_ventas", "columns": [{"name": "fecha_id"}],
             "measures": [{"name": "total_ventas"}]},
            {"name": "dim_fecha", "columns": [{"name": "fecha_id"}], "measures": []},
        ],
        "relationships": [
            {"fromTable": "fact_ventas", "fromColumn": "fecha_id",
             "toTable": "dim_fecha", "toColumn": "fecha_id", "isActive": True},
        ],
        "expressions": [
            "let Source = AzureStorage.DataLake.Contents(\"https://onelake...\") in Source"
        ],
    }
}

# Known defect: the declared relationship is missing. This is the pattern the
# gate has to catch: relationships that do not point where they are believed to.
MODEL_BIM_SIN_RELACION = json.loads(json.dumps(MODEL_BIM_OK))
MODEL_BIM_SIN_RELACION["model"]["relationships"] = []

VISUAL_OK = {
    "visual": {"query": {"Select": [
        {"Column": "fecha_id"},
        {"Measure": "total_ventas"},
    ]}}
}

# Known defect: a referenced field that does not exist in the model (a typo,
# renombre, o filtro/campo huerfano).
VISUAL_HUERFANO = {
    "visual": {"query": {"Select": [
        {"Column": "columna_que_no_existe"},
    ]}}
}


# --- One case per verifier ---------------------------------------------------

def caso_contrato(tmp: Path) -> tuple[int, int]:
    contract = tmp / "core.dim_fecha.yml"
    _write(contract, CONTRATO_YML)
    esquema_ok = tmp / "esquema_ok.json"
    _write(esquema_ok, json.dumps(ESQUEMA_OK, indent=2))
    esquema_bad = tmp / "esquema_bad.json"
    _write(esquema_bad, json.dumps(ESQUEMA_FALTA_COLUMNA, indent=2))

    ok = _run("verify_contract.py", [str(contract), "--schema", str(esquema_ok)], tmp)
    bad = _run("verify_contract.py", [str(contract), "--schema", str(esquema_bad)], tmp)
    return ok, bad


def caso_diff(tmp: Path) -> tuple[int, int]:
    def _repo(name: str) -> Path:
        repo = tmp / name
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "autoverificar@faw.local")
        _git(repo, "config", "user.name", "autoverificar")
        _write(repo / "notebook.json", NOTEBOOK_BASE)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
        return repo

    repo_ok = _repo("diff_ok")
    _write(repo_ok / "notebook.json", NOTEBOOK_CAMBIO_COSMETICO)
    ok = _run("verify_diff.py", [], repo_ok)

    repo_bad = _repo("diff_bad")
    _write(repo_bad / "notebook.json", NOTEBOOK_CAMBIO_METADATA)
    bad = _run("verify_diff.py", [], repo_bad)
    return ok, bad


def caso_modelo(tmp: Path) -> tuple[int, int]:
    expected = tmp / "ventas.expected.yml"
    _write(expected, MODEL_ESPERADO_YML)
    def_ok = tmp / "model_ok.bim.json"
    _write(def_ok, json.dumps(MODEL_BIM_OK, indent=2))
    def_bad = tmp / "model_bad.bim.json"
    _write(def_bad, json.dumps(MODEL_BIM_SIN_RELACION, indent=2))

    ok = _run("verify_model.py", [str(expected), "--definition", str(def_ok)], tmp)
    bad = _run("verify_model.py", [str(expected), "--definition", str(def_bad)], tmp)
    return ok, bad


def caso_reporte(tmp: Path) -> tuple[int, int]:
    model = tmp / "model.bim.json"
    _write(model, json.dumps(MODEL_BIM_OK, indent=2))

    rep_ok = tmp / "MiReporte_ok.Report"
    _write(rep_ok / "visual.json", json.dumps(VISUAL_OK, indent=2))
    ok = _run("verify_report.py", ["--report", str(rep_ok), "--model", str(model)], tmp)

    rep_bad = tmp / "MiReporte_bad.Report"
    _write(rep_bad / "visual.json", json.dumps(VISUAL_HUERFANO, indent=2))
    bad = _run("verify_report.py", ["--report", str(rep_bad), "--model", str(model)], tmp)
    return ok, bad


CONTRATO_B_YML = CONTRATO_YML.replace("core.dim_fecha", "core.dim_moneda")

PERFIL_MD = (
    "# Synthetic profiling receipt for the self-check\n\n"
    "Input for the multi-table contract gate canary. This text only needs "
    "to exceed the 200-byte minimum the 'profile' gate requires "
    "so the run can reach DESIGN and test what actually matters here: "
    "that DESIGN->BUILD requires the contract receipt of EVERY declared "
    "table, not only of the last one issued.\n"
)


def caso_estado_contrato_multitabla(tmp: Path) -> tuple[int, int]:
    """
    Regression case: an ARTIFACT ticket covering several tables used to close
    DESIGN with the receipt of the last table verified, because the 'contract'
    receipt was a single file each run overwrote.

    should-fail case: 2 tables declared, 1 verified -> the move must be rejected.
    should-pass case: the 2nd table is verified -> the same move must pass.
    """
    caja = tmp / "caja"
    caja.mkdir()
    _write(caja / "core.dim_fecha.yml", CONTRATO_YML)
    _write(caja / "core.dim_moneda.yml", CONTRATO_B_YML)
    # The path mirrors the real structure (docs/faw/<ticket>/): the `profile`
    # gate requires the receipt to be attributable to the open ticket.
    _write(caja / "docs" / "faw" / "CANARY-1" / "profiling.md", PERFIL_MD)

    def state(*args: str) -> int:
        return _run("state.py", list(args), caja)

    if state("start", "--ticket", "CANARY-1", "--tier", "ARTIFACT",
              "--title", "multitabla") != 0:
        raise RuntimeError("could not start the synthetic ticket")
    if state("move", "--to", "PROFILING",
              "--gate", "user_confirmation=canary") != 0:
        raise RuntimeError("could not move to PROFILING")
    if state("move", "--to", "DESIGN", "--gate", "profile=docs/faw/CANARY-1/profiling.md") != 0:
        raise RuntimeError("could not move to DESIGN")

    # Only ONE of the two tables is verified...
    if _run("verify_contract.py",
            ["core.dim_fecha.yml", "--syntax-only"], caja) != 0:
        raise RuntimeError("synthetic contract A failed the syntax check")

    # ...and the move declares TWO: it has to be rejected.
    bad = state("move", "--to", "BUILD",
                 "--gate", "tables=core.dim_fecha,core.dim_moneda",
                 "--gate", "user_confirmation=canary")

    # With the second table verified, the same move has to pass.
    if _run("verify_contract.py",
            ["core.dim_moneda.yml", "--syntax-only"], caja) != 0:
        raise RuntimeError("synthetic contract B failed the syntax check")
    ok = state("move", "--to", "BUILD",
                "--gate", "tables=core.dim_fecha,core.dim_moneda",
                "--gate", "user_confirmation=canary")
    return ok, bad


GOOD_BRIEF = """# Report brief: CANARY-B

## Objective
Enable the finance lead to decide each week which overdue accounts to escalate,
replacing a manual spreadsheet that is assembled by hand every Monday morning.

## Audience
The finance lead and the two analysts on the collections team, weekly.

## Questions it answers
1. Which accounts crossed 90 days overdue this week?
2. How does the overdue total move month over month?
3. Which customers concentrate the top ten percent of overdue balance?

## Out of scope
No forecasting, no write-off proposals, no per-agent performance view.

## Data source
Semantic model SM_Collections in the finance workspace, tables fact_balance
and dim_customer.

## Business validation
The finance lead confirms the totals against the monthly close report.
"""

# Known defect: the template placeholders survive and the sections are hollow.
# This is exactly what the gate exists to reject, and what a size check alone
# would have accepted.
BAD_BRIEF = """# Report brief: CANARY-B

## Objective
<What this report exists for. Which decision it enables, or which question it
closes. If the answer is "to see the data", there is no objective yet.>

## Audience
<Who will open it, in what role, and how often.>

## Questions it answers
1. <...?>

## Out of scope
<What is NOT included.>

## Data source
<Semantic model, workspace, connection type and tables consumed.>
"""


def caso_brief(tmp: Path) -> tuple[int, int]:
    good = tmp / "good-brief.md"
    bad = tmp / "bad-brief.md"
    _write(good, GOOD_BRIEF)
    _write(bad, BAD_BRIEF)
    ok = _run("verify_brief.py", ["--brief", str(good)], tmp)
    bad_rc = _run("verify_brief.py", ["--brief", str(bad)], tmp)
    return ok, bad_rc


def caso_plataforma(tmp: Path) -> tuple[int, int]:
    """Both cases run with --offline, so the outcome depends only on precedent
    in the repository and never on the network."""
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "selfcheck@faw.local")
    _git(repo, "config", "user.name", "selfcheck")

    real = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/1.0.0/schema.json"
    fake = "https://developer.microsoft.com/json-schemas/fabric/invented/by/analogy/9.9.9/schema.json"

    # The literal gains precedent by existing in a committed file.
    _write(repo / "existing.json", '{"$schema": "%s"}' % real)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    # Should pass: a staged file reusing the literal that HEAD already carries.
    _write(repo / "new_ok.json", '{"$schema": "%s"}' % real)
    _git(repo, "add", "new_ok.json")
    ok = _run("verify_platform.py", ["--offline"], repo)

    # Should fail: a staged literal with no precedent, and no network to save it.
    _git(repo, "reset", "-q")
    _write(repo / "new_bad.json", '{"$schema": "%s"}' % fake)
    _git(repo, "add", "new_bad.json")
    bad_rc = _run("verify_platform.py", ["--offline"], repo)
    return ok, bad_rc


def caso_raiz_gobernada(tmp: Path) -> tuple[int, int]:
    """The governed folder is found from a subdirectory, and only from inside it.

    This is the case that motivated `project.root()`. Before it, governance
    depended on `.faw/` being a direct child of the reported directory: a session
    standing one level down was ungoverned, and the hook said nothing about it —
    exit 0 with no output, indistinguishable from a hook that evaluated and
    allowed. That is the failure mode principle 4 forbids, so it gets a case.
    """
    folder = tmp / "working-folder"
    deep = folder / "docs" / "faw" / "T-001"
    deep.mkdir(parents=True)
    _write(folder / ".faw" / "state.jsonl", json.dumps({
        "ticket": "T-001", "tier": "MINOR-CHANGE", "phase": "BUILD",
        "title": "case", "ts": "2026-01-01T00:00:00+00:00",
    }) + "\n")

    # Should pass: standing two levels down, the folder above is still governed.
    injected = _hook("inject_context.py", {"cwd": str(deep), "prompt": "x"})
    ok = 0 if "T-001" in injected else 1

    # Should fail: an unrelated tree has no `.faw/` in any parent, so the hook
    # has to stay quiet. A method that injects itself everywhere is not opt-in.
    outside = tmp / "unrelated"
    outside.mkdir()
    quiet = _hook("inject_context.py", {"cwd": str(outside), "prompt": "x"})
    bad_rc = 1 if quiet == "" else 0
    return ok, bad_rc
# A tool name is CamelCase, or an MCP name, optionally with a trailing glob.
# Checking the shape rather than a list of known names is deliberate: the set of
# available tools changes with every MCP server connected, and a hardcoded list
# would age into false failures.
RE_TOOL_NAME = re.compile(r"^(?:[A-Z][A-Za-z0-9]*|mcp__[\w.*-]+(?:__[\w.*-]+)?)$")

VALID_AGENT = """---
name: canary-validator
description: A synthetic agent used by the self-check.
disallowedTools: Edit, NotebookEdit
model: opus
---

Body.
"""

# Known defect: `tools` holds prose instead of a list. Claude Code splits it on
# whitespace, resolves neither token to a real tool, and refuses to launch the
# agent. Nothing catches this until someone invokes it, which is how the
# validator shipped unusable and the VALIDATION phase became unreachable.
BROKEN_AGENT = """---
name: canary-broken
description: A synthetic agent with prose where a tool list belongs.
tools: All tools
model: opus
---

Body.
"""


def _agent_frontmatter_errors(path: Path) -> list[str]:
    """Errors in the frontmatter of one distributed agent. Empty means valid."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return [f"{path.name}: no frontmatter"]
    end = text.find("\n---", 3)
    if end == -1:
        return [f"{path.name}: unterminated frontmatter"]

    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

    errors = []
    for required in ("name", "description"):
        if not fields.get(required):
            errors.append(f"{path.name}: '{required}' is missing")

    for field in ("tools", "disallowedTools"):
        raw = fields.get(field)
        if raw is None:
            continue
        if not raw:
            errors.append(f"{path.name}: '{field}' is present and empty")
            continue
        for token in (t.strip() for t in raw.replace(",", " ").split()):
            if not RE_TOOL_NAME.match(token):
                errors.append(f"{path.name}: '{field}' contains '{token}', which is not "
                              f"a tool name. The field takes a list, not prose")
    return errors


def caso_agentes(tmp: Path) -> tuple[int, int]:
    """The distributed agents must have a frontmatter Claude Code can resolve.

    A broken one fails only at the moment of launching the agent, with nothing
    else detecting it. The should-pass case runs against the real agents/ of the
    repository, so this also guards what actually ships.
    """
    real = ROOT / "agents"
    ok = 1 if any(_agent_frontmatter_errors(f) for f in sorted(real.glob("*.md"))) else 0

    fake = tmp / "agents"
    fake.mkdir(parents=True, exist_ok=True)
    _write(fake / "valid.md", VALID_AGENT)
    _write(fake / "broken.md", BROKEN_AGENT)
    bad = 1 if any(_agent_frontmatter_errors(f) for f in sorted(fake.glob("*.md"))) else 0
    return ok, bad


CASOS = [
    ("agents frontmatter", caso_agentes),
    ("verify_contract.py", caso_contrato),
    ("verify_diff.py", caso_diff),
    ("verify_model.py", caso_modelo),
    ("verify_report.py", caso_reporte),
    ("verify_brief.py", caso_brief),
    ("verify_platform.py", caso_plataforma),
    ("state.py (contract multi-table)", caso_estado_contrato_multitabla),
    ("hooks (governed root resolution)", caso_raiz_gobernada),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    tmp_root = Path(tempfile.mkdtemp(prefix="faw-autoverificar-"))
    results: list[tuple[str, bool, str]] = []
    try:
        for name, fn in CASOS:
            tmp = tmp_root / name.replace(".py", "")
            tmp.mkdir(parents=True, exist_ok=True)
            try:
                ok_code, bad_code = fn(tmp)
            except Exception as e:  # noqa: BLE001 - a broken case is a FAIL to report, not a crash
                results.append((name, False, f"exception while building the case: {e}"))
                continue
            ok_good = ok_code == 0
            bad_good = bad_code == 1
            results.append((
                name, ok_good and bad_good,
                f"should-pass exit={ok_code} ({'OK' if ok_good else 'WRONG, expected 0'}), "
                f"should-fail exit={bad_code} ({'OK' if bad_good else 'WRONG, expected 1'})",
            ))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print("\n=== self-check summary ===")
    hubo_falla = False
    for name, ok, detail in results:
        verdict = "PASS" if ok else "FAIL"
        hubo_falla = hubo_falla or not ok
        print(f"  verifier {name}: {verdict}  ({detail})")
    print()
    return 1 if hubo_falla else 0


if __name__ == "__main__":
    sys.exit(main())
