#!/usr/bin/env python3
"""
Compuerta `plataforma` — impide comitear literales de Microsoft inventados.

## Por que existe

Un literal de plataforma de Microsoft (un `$schema`, un `connectionString`) se
inventa facil por analogia con otro que ya se vio, y el resultado parece
correcto hasta que la herramienta lo rechaza. Tres formas tipicas en que esto
pasa:

1. `$schema` del `.pbip`: escribir `.../item/report/pbipProperties/1.0.0/...`
   cuando el real es `.../fabric/pbip/pbipProperties/1.0.0/...`. Power BI
   Desktop lo rechaza con un dialogo de error.
2. `$schema` de `definition.pbir`: escribir `.../definition.pbir/1.0.0/...`
   cuando el real es `.../definitionProperties/2.0.0/...`.
3. `connectionString` de `byConnection`: escribir un string XMLA a mano cuando
   el real que emite Desktop lleva ademas `initial catalog`, `access mode`,
   `integrated security` y `semanticmodelid`.

El principio 6 ("afirmaciones sobre la plataforma: documentacion oficial leida")
ya prohibe esto. Que este escrito no alcanza si nada lo verifica: los tres casos
se resuelven igual — copiando de un artefacto real ya existente, o resolviendo
la URL. Las dos cosas son mecanizables, y esto las mecaniza.

## Que hace

Sobre lo que esta por comitearse (o `--todo` sobre el arbol), busca literales de
plataforma y exige que cada uno cumpla UNA de dos condiciones:

  a) **Precedente**: el mismo literal ya aparece en un archivo commiteado del
     repo. Si Fabric lo escribio antes, es real.
  b) **Resoluble**: si es una URL, responde HTTP 200.

Un literal que no cumple ninguna de las dos no esta verificado: es una analogia.

## Lo que NO hace

No valida semantica. Una URL de schema puede existir y ser la equivocada para
ese tipo de archivo (`page/2.1.0` en un `visual.json` resuelve y esta mal). Para
eso esta el validador del fabricante — en PBIR, `powerbi-report-author validate`.
Esta compuerta atrapa lo inventado, no lo mal elegido.

Uso
---
  python verificar_plataforma.py              # sobre el diff staged
  python verificar_plataforma.py --todo       # sobre todo el arbol trackeado
  python verificar_plataforma.py --sin-red    # solo precedente, sin resolver URLs

Salida: 0 si todo verifica (emite recibo), 1 si hay literales sin verificar,
2 si los insumos estan mal.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import recibos  # noqa: E402

# Literales de plataforma que se inventan por analogia. Cada patron nace de un
# error real, no de imaginar que podria salir mal.
PATRONES = {
    "schema-url": re.compile(r'https://developer\.microsoft\.com/json-schemas/[^\s"\'<>]+'),
    "expression-source": re.compile(r"DirectLake\s*-\s*[A-Za-z0-9_]+"),
}

# Los connection strings van por otro camino, y la primera version se equivoco
# tratandolos como los demas literales: el regex cortaba en el primer espacio de
# un display name con espacios (ej. un workspace "[DEV] Ventas") y marcaba como
# inventado el string que habia escrito Power BI Desktop. Un connection string
# no se verifica por precedente (suele ser
# unico) ni por HTTP (no es una URL de red). Lo que SI se puede verificar es su
# FORMA — y es exactamente lo que distinguia al real del inventado: el que se
# escribio a mano tenia solo "Data Source" e "initial catalog", y le faltaba todo
# lo que Desktop agrega.
MARCA_CONEXION = "powerbi://"
CLAVES_CONEXION = ("data source", "initial catalog", "semanticmodelid")

EXTENSIONES = {".json", ".pbir", ".pbip", ".pbism", ".tmdl", ".py", ".md", ".yml", ".yaml"}

# Rutas que no cuentan como precedente ni se escanean: son documentacion del
# propio metodo, donde estos literales aparecen como ejemplo.
EXCLUIR = ("docs/faw/", ".faw/", "faw/contratos/PLANTILLA")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def _archivos(todo: bool) -> list[str]:
    salida = _git("ls-files") if todo else _git("diff", "--cached", "--name-only")
    return [f for f in salida.splitlines() if f.strip()]


def _relevante(ruta: str) -> bool:
    if any(x in ruta for x in EXCLUIR):
        return False
    return Path(ruta).suffix.lower() in EXTENSIONES


def _literales(texto: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for nombre, rx in PATRONES.items():
        for m in rx.findall(texto):
            out.setdefault(nombre, set()).add(m.rstrip('.,;:"\''))
    return out


def _precedente(literal: str, archivo_actual: str) -> str | None:
    """Busca el literal en la version COMMITEADA del repo (HEAD), no en el arbol."""
    salida = _git("grep", "-l", "--fixed-strings", literal, "HEAD", "--")
    for linea in salida.splitlines():
        # `git grep ... HEAD` devuelve "HEAD:ruta"
        ruta = linea.split(":", 1)[-1].strip()
        if ruta and ruta != archivo_actual and not any(x in ruta for x in EXCLUIR):
            return ruta
    return None


def _resuelve(url: str, cache: dict[str, bool]) -> bool:
    if url in cache:
        return cache[url]
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "faw-verificar-plataforma"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            ok = 200 <= r.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        ok = False
    cache[url] = ok
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Compuerta de plataforma de FAW")
    p.add_argument("--todo", action="store_true",
                   help="escanea todo el arbol trackeado en vez del diff staged")
    p.add_argument("--sin-red", action="store_true",
                   help="no intenta resolver URLs; solo acepta precedente en el repo")
    a = p.parse_args()

    if not _git("rev-parse", "--git-dir").strip():
        print("ERROR: no es un repo git", file=sys.stderr)
        return 2

    archivos = [f for f in _archivos(a.todo) if _relevante(f)]
    print(f"\n=== Plataforma — {'arbol completo' if a.todo else 'diff staged'} ===")
    print(f"  archivos relevantes: {len(archivos)}")

    if not archivos:
        print("\n  nada que verificar\n\n  PASA\n")
        recibos.emitir("plataforma", "verificar_plataforma.py", [],
                       "sin archivos relevantes en el alcance")
        return 0

    cache: dict[str, bool] = {}
    total = 0
    verificados: list[tuple[str, str, str]] = []
    sin_verificar: list[tuple[str, str, str]] = []

    for ruta in archivos:
        pth = Path(ruta)
        if not pth.exists():
            continue
        try:
            texto = pth.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # --- Connection strings: chequeo de forma, no de precedente ---
        if MARCA_CONEXION in texto.lower():
            total += 1
            bajo = texto.lower()
            faltan = [c for c in CLAVES_CONEXION if c not in bajo]
            if faltan:
                sin_verificar.append((
                    ruta,
                    f"connection string a {MARCA_CONEXION}...",
                    f"[connection-string] le faltan claves que emite la herramienta: "
                    f"{', '.join(faltan)}",
                ))
            else:
                verificados.append((ruta, f"connection string a {MARCA_CONEXION}...",
                                    "tiene la forma completa que emite la herramienta"))

        for tipo, literales in _literales(texto).items():
            for lit in literales:
                total += 1
                prec = _precedente(lit, ruta)
                if prec:
                    verificados.append((ruta, lit, f"precedente en {prec}"))
                    continue
                if lit.startswith("https://") and not a.sin_red:
                    if _resuelve(lit, cache):
                        verificados.append((ruta, lit, "resuelve HTTP 200"))
                        continue
                    sin_verificar.append((ruta, lit, "no resuelve y no tiene precedente"))
                    continue
                sin_verificar.append((ruta, lit, f"[{tipo}] sin precedente en el repo"))

    print(f"  literales de plataforma encontrados: {total}")
    for ruta, lit, motivo in verificados:
        print(f"    ok   {lit[:88]}  ({motivo})")

    if sin_verificar:
        print(f"\n  [ERROR] {len(sin_verificar)} literales SIN VERIFICAR:")
        for ruta, lit, motivo in sin_verificar:
            print(f"      {ruta}")
            print(f"        {lit}")
            print(f"        -> {motivo}")
        print("\n  Un literal de plataforma sin precedente ni resolucion es una analogia,\n"
              "  no un dato (principio 6). Como resolverlo:\n"
              "    - Copiarlo de un artefacto real que la herramienta ya haya escrito\n"
              "      (otro .Report del repo, un item sincronizado desde el workspace).\n"
              "    - O dejar que la herramienta lo genere y comitear ESO.\n"
              "    - O leer la doc oficial y verificar la URL exacta.\n\n  FALLA\n")
        recibos.invalidar("plataforma")
        return 1

    print("\n  PASA\n")
    recibos.emitir("plataforma", "verificar_plataforma.py", [],
                   f"{total} literales de plataforma, todos con precedente o resolucion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
