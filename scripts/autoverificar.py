#!/usr/bin/env python3
"""
Auto-verificacion de las compuertas de FAW (canary / mutation-testing minimo de
los propios verificadores).

Por que existe
---------------
Las compuertas de `estado.py` son tan confiables como los scripts que las
implementan (`verificar_contrato.py`, `verificar_diff.py`, `verificar_modelo.py`,
`verificar_reporte.py`). Nada garantiza que sigan detectando lo que dicen
detectar con el tiempo: un cambio accidental en una regex, una condicion
invertida, o un campo que se deja de leer puede dejar un verificador "verde"
para siempre sin que nadie lo note hasta que falle en produccion. Ya paso una
vez con `estado.py` aceptando que el agente declarara `"ok: ..."` sin correr
nada real (arreglado con los recibos firmados de `faw/recibos.py`); esto cubre
la pregunta que quedo abierta despues de ese arreglo.

Este script no reemplaza revision humana ni prueba exhaustiva. Para cada
verificador arma, en un directorio temporal (nunca dentro del repo), un insumo
que DEBERIA pasar (exit 0) y un insumo con un defecto puntual y conocido que
DEBERIA hacerlo fallar (exit 1): una columna de esquema que no coincide con el
contrato, un diff que si toca metadata protegida, una relacion de modelo que
falta, un campo de reporte que no existe en el modelo. Si el caso
"deberia fallar" en realidad pasa (o el caso "deberia pasar" en realidad
falla), el verificador tiene un agujero y este script termina con exit 1.

El repo hermano DAW (dilux-agentic-workflow) resuelve un problema analogo con
`scripts/mutate.py` -- leido completo antes de escribir este archivo. Ese script
inyecta mutaciones de codigo en los propios scripts de DAW (~100 mutaciones) y
corre `scripts/verify_install.sh` completo contra cada copia mutada, en un
directorio temporal. Es mutation testing real, pero fuertemente acoplado a
infraestructura que FAW no tiene: los adapters multi-herramienta de DAW, su
`verify_install.sh`, su `transition-graph.json` propio. Portarlo tal cual no es
proporcional al tamano de FAW. Lo que se adopta aca es la idea de fondo que
`docs/RATIONALE.md` de DAW nombra explicitamente ("mutation testing es el
medidor, no el detector": sirve para confirmar que una compuerta conocida sigue
funcionando, no para descubrir fallas nuevas) -- expresada como un par de
insumos bueno/malo por verificador, no como mutacion de codigo.

Uso
---
    python scripts/autoverificar.py

Exit 0 si todos los casos se comportaron como se esperaba hoy. Exit 1 si
alguno no. Ademas de los verificadores sueltos hay un caso de punta a punta
contra `estado.py` (la compuerta `contrato` con varias tablas), porque el gap
que motivo ese caso estaba en la compuerta, no en el verificador.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
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


# ── Fixtures ──────────────────────────────────────────────────────────────

CONTRATO_YML = """\
tabla: core.dim_fecha
capa: gold
grano: "una fila por fecha"
clave_natural:
  - fecha_id
columnas:
  - nombre: fecha_id
    tipo: int
    nulable: false
  - nombre: fecha
    tipo: date
    nulable: false
calidad:
  - regla: unicidad
    columnas: [fecha_id]
"""

ESQUEMA_OK = {
    "tabla": "core.dim_fecha",
    "medido_en": "2026-08-03T00:00:00Z",
    "filas": 100,
    "columnas": [
        {"nombre": "fecha_id", "tipo": "int", "nulable": False},
        {"nombre": "fecha", "tipo": "date", "nulable": False},
    ],
}

# Defecto conocido: falta la columna 'fecha' -- el caso que la compuerta de
# esquema existe para atrapar (fila-count correcto, columna ausente).
ESQUEMA_FALTA_COLUMNA = {
    "tabla": "core.dim_fecha",
    "medido_en": "2026-08-03T00:00:00Z",
    "filas": 100,
    "columnas": [
        {"nombre": "fecha_id", "tipo": "int", "nulable": False},
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

# Cambio cosmetico: solo el texto de la celda. No deberia disparar la compuerta.
NOTEBOOK_CAMBIO_COSMETICO = NOTEBOOK_BASE.replace("hola mundo", "chau mundo")

# Defecto conocido: cambia default_lakehouse, que es lo que deja un notebook
# sin poder ejecutarse y lo que esta compuerta tiene que atrapar.
NOTEBOOK_CAMBIO_METADATA = NOTEBOOK_BASE.replace("lh-bronze-0001", "lh-bronze-9999")

MODELO_ESPERADO_YML = """\
modelo: ventas
tablas:
  - fact_ventas
  - dim_fecha
modo: directlake_onelake
relaciones:
  - desde_tabla: fact_ventas
    desde_columna: fecha_id
    hacia_tabla: dim_fecha
    hacia_columna: fecha_id
    activa: true
medidas:
  - total_ventas
"""

MODELO_BIM_OK = {
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

# Defecto conocido: falta la relacion declarada -- el patron que esta compuerta
# tiene que atrapar (relaciones que no apuntan donde se cree).
MODELO_BIM_SIN_RELACION = json.loads(json.dumps(MODELO_BIM_OK))
MODELO_BIM_SIN_RELACION["model"]["relationships"] = []

VISUAL_OK = {
    "visual": {"query": {"Select": [
        {"Column": "fecha_id"},
        {"Measure": "total_ventas"},
    ]}}
}

# Defecto conocido: un campo referenciado que no existe en el modelo (typo,
# renombre, o filtro/campo huerfano).
VISUAL_HUERFANO = {
    "visual": {"query": {"Select": [
        {"Column": "columna_que_no_existe"},
    ]}}
}


# ── Casos por verificador ────────────────────────────────────────────────

def caso_contrato(tmp: Path) -> tuple[int, int]:
    contrato = tmp / "core.dim_fecha.yml"
    _write(contrato, CONTRATO_YML)
    esquema_ok = tmp / "esquema_ok.json"
    _write(esquema_ok, json.dumps(ESQUEMA_OK, indent=2))
    esquema_bad = tmp / "esquema_bad.json"
    _write(esquema_bad, json.dumps(ESQUEMA_FALTA_COLUMNA, indent=2))

    ok = _run("verificar_contrato.py", [str(contrato), "--esquema", str(esquema_ok)], tmp)
    bad = _run("verificar_contrato.py", [str(contrato), "--esquema", str(esquema_bad)], tmp)
    return ok, bad


def caso_diff(tmp: Path) -> tuple[int, int]:
    def _repo(nombre: str) -> Path:
        repo = tmp / nombre
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
    ok = _run("verificar_diff.py", [], repo_ok)

    repo_bad = _repo("diff_bad")
    _write(repo_bad / "notebook.json", NOTEBOOK_CAMBIO_METADATA)
    bad = _run("verificar_diff.py", [], repo_bad)
    return ok, bad


def caso_modelo(tmp: Path) -> tuple[int, int]:
    esperado = tmp / "ventas.esperado.yml"
    _write(esperado, MODELO_ESPERADO_YML)
    def_ok = tmp / "model_ok.bim.json"
    _write(def_ok, json.dumps(MODELO_BIM_OK, indent=2))
    def_bad = tmp / "model_bad.bim.json"
    _write(def_bad, json.dumps(MODELO_BIM_SIN_RELACION, indent=2))

    ok = _run("verificar_modelo.py", [str(esperado), "--definicion", str(def_ok)], tmp)
    bad = _run("verificar_modelo.py", [str(esperado), "--definicion", str(def_bad)], tmp)
    return ok, bad


def caso_reporte(tmp: Path) -> tuple[int, int]:
    modelo = tmp / "model.bim.json"
    _write(modelo, json.dumps(MODELO_BIM_OK, indent=2))

    rep_ok = tmp / "MiReporte_ok.Report"
    _write(rep_ok / "visual.json", json.dumps(VISUAL_OK, indent=2))
    ok = _run("verificar_reporte.py", ["--reporte", str(rep_ok), "--modelo", str(modelo)], tmp)

    rep_bad = tmp / "MiReporte_bad.Report"
    _write(rep_bad / "visual.json", json.dumps(VISUAL_HUERFANO, indent=2))
    bad = _run("verificar_reporte.py", ["--reporte", str(rep_bad), "--modelo", str(modelo)], tmp)
    return ok, bad


CONTRATO_B_YML = CONTRATO_YML.replace("core.dim_fecha", "core.dim_moneda")

PERFIL_MD = (
    "# Perfilado sintetico para autoverificar\n\n"
    "Insumo del canary de la compuerta contrato multi-tabla. Este texto solo "
    "necesita superar el minimo de 200 bytes que exige la compuerta 'perfil' "
    "para poder llegar a DISENO y probar lo que de verdad se quiere probar: "
    "que DISENO->CONSTRUCCION exija el recibo de contrato de CADA tabla "
    "declarada, no solo del ultimo emitido.\n"
)


def caso_estado_contrato_multitabla(tmp: Path) -> tuple[int, int]:
    """
    Caso de regresion: un ticket ARTEFACTO que toca varias tablas cerraba
    DISENO con el recibo de la ultima tabla verificada, porque el recibo de
    'contrato' era un archivo unico que cada corrida pisaba.

    caso-debe-fallar: 2 tablas declaradas, 1 verificada -> mover debe rechazar.
    caso-debe-pasar : se verifica la 2da tabla -> el mismo mover debe pasar.
    """
    caja = tmp / "caja"
    caja.mkdir()
    _write(caja / "core.dim_fecha.yml", CONTRATO_YML)
    _write(caja / "core.dim_moneda.yml", CONTRATO_B_YML)
    _write(caja / "perfilado.md", PERFIL_MD)

    def estado(*args: str) -> int:
        return _run("estado.py", list(args), caja)

    if estado("iniciar", "--ticket", "CANARY-1", "--tier", "ARTEFACTO",
              "--titulo", "multitabla") != 0:
        raise RuntimeError("no se pudo iniciar el ticket sintetico")
    if estado("mover", "--a", "PERFILADO",
              "--compuerta", "confirmacion_usuario=canary") != 0:
        raise RuntimeError("no se pudo mover a PERFILADO")
    if estado("mover", "--a", "DISENO", "--compuerta", "perfil=perfilado.md") != 0:
        raise RuntimeError("no se pudo mover a DISENO")

    # Se verifica UNA sola de las dos tablas...
    if _run("verificar_contrato.py",
            ["core.dim_fecha.yml", "--solo-sintaxis"], caja) != 0:
        raise RuntimeError("el contrato sintetico A no paso sintaxis")

    # ...y el mover declara DOS: tiene que rechazar.
    bad = estado("mover", "--a", "CONSTRUCCION",
                 "--compuerta", "tablas=core.dim_fecha,core.dim_moneda",
                 "--compuerta", "confirmacion_usuario=canary")

    # Con la segunda tabla verificada, el mismo mover tiene que pasar.
    if _run("verificar_contrato.py",
            ["core.dim_moneda.yml", "--solo-sintaxis"], caja) != 0:
        raise RuntimeError("el contrato sintetico B no paso sintaxis")
    ok = estado("mover", "--a", "CONSTRUCCION",
                "--compuerta", "tablas=core.dim_fecha,core.dim_moneda",
                "--compuerta", "confirmacion_usuario=canary")
    return ok, bad


CASOS = [
    ("verificar_contrato.py", caso_contrato),
    ("verificar_diff.py", caso_diff),
    ("verificar_modelo.py", caso_modelo),
    ("verificar_reporte.py", caso_reporte),
    ("estado.py (contrato multi-tabla)", caso_estado_contrato_multitabla),
]


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="faw-autoverificar-"))
    resultados: list[tuple[str, bool, str]] = []
    try:
        for nombre, fn in CASOS:
            tmp = tmp_root / nombre.replace(".py", "")
            tmp.mkdir(parents=True, exist_ok=True)
            try:
                ok_code, bad_code = fn(tmp)
            except Exception as e:  # noqa: BLE001 - un caso roto es una FALLA a reportar, no un crash
                resultados.append((nombre, False, f"excepcion armando el caso: {e}"))
                continue
            ok_bien = ok_code == 0
            bad_bien = bad_code == 1
            resultados.append((
                nombre, ok_bien and bad_bien,
                f"caso-debe-pasar exit={ok_code} ({'OK' if ok_bien else 'MAL, esperaba 0'}), "
                f"caso-debe-fallar exit={bad_code} ({'OK' if bad_bien else 'MAL, esperaba 1'})",
            ))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print("\n=== autoverificar - resumen ===")
    hubo_falla = False
    for nombre, ok, detalle in resultados:
        estado = "PASA" if ok else "FALLA"
        hubo_falla = hubo_falla or not ok
        print(f"  verificador {nombre}: {estado}  ({detalle})")
    print()
    return 1 if hubo_falla else 0


if __name__ == "__main__":
    sys.exit(main())
