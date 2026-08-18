#!/usr/bin/env python3
"""
Compuerta `reporte` — el fallo silencioso de la capa de reportes es el filtro
de desarrollo olvidado ("solo cliente X para probar", "solo 2025") persistido
en el archivo del reporte. Publica numeros creibles y filtrados. Es el
equivalente exacto de la FK nula: invisible en la vista que se usa para
revisarlo, porque nadie mira el JSON de filtros antes de publicar.

Este script hace DOS cosas de fuerza distinta, a propósito:

1. **Dump de filtros persistidos** (recibo — lo revisa un humano). Recorre
   TODOS los .json del proyecto de reporte buscando cualquier clave "filters"
   /"Filters", sin asumir una version puntual del schema. Es deliberadamente
   agnostico al formato exacto: el PBIR de Power BI es un formato relativamente
   nuevo y no tengo, en este momento, una lectura verificada de su especificacion
   completa contra la doc oficial de Microsoft. Antes de confiar en esto para
   un caso real, contrastar contra la documentacion vigente de PBIP/PBIR
   (regla de rigor de FAW: nada de sintaxis de Microsoft inventada por analogia).

2. **Campos referenciados por visual, contra el modelo** (heuristica, primera
   iteracion). Busca patrones "Column"/"Measure``/"Property" en los JSON y los
   cruza contra las tablas/columnas/medidas reales del model.bim. Es un primer
   intento y hay que afinarlo contra un .pbip real la primera vez que se use en
   serio: se declara asi, no como verificacion garantizada.

Uso
---
  python verificar_reporte.py --reporte "MiReporte.Report" --modelo model.bim.json

Salida: 0 si no encuentra filtros sin revisar Y todos los campos resuelven,
1 si hay algo para que un humano mire, 2 si los insumos estan mal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import recibos  # noqa: E402


def _buscar_filtros(nodo, ruta_archivo: str, hallados: list[dict], camino: str = "") -> None:
    """Recorre cualquier estructura JSON buscando claves de filtro, sin asumir schema."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            nuevo_camino = f"{camino}.{clave}" if camino else clave
            if clave.lower() == "filters" and valor:
                hallados.append({"archivo": ruta_archivo, "en": nuevo_camino, "valor": valor})
            else:
                _buscar_filtros(valor, ruta_archivo, hallados, nuevo_camino)
    elif isinstance(nodo, list):
        for i, item in enumerate(nodo):
            _buscar_filtros(item, ruta_archivo, hallados, f"{camino}[{i}]")


def _buscar_campos(nodo, encontrados: set[str]) -> None:
    """Heuristica: junta valores de claves tipicas de referencia a campo en PBIR."""
    if isinstance(nodo, dict):
        for clave in ("Column", "Measure", "Property", "Hierarchy"):
            if clave in nodo and isinstance(nodo[clave], str):
                encontrados.add(nodo[clave])
        for v in nodo.values():
            _buscar_campos(v, encontrados)
    elif isinstance(nodo, list):
        for item in nodo:
            _buscar_campos(item, encontrados)


def campos_del_modelo(modelo: dict) -> set[str]:
    m = modelo.get("model", modelo)
    campos: set[str] = set()
    for t in m.get("tables", []):
        for c in t.get("columns", []):
            campos.add(c["name"])
        for med in t.get("measures", []):
            campos.add(med["name"])
    return campos


def main() -> int:
    p = argparse.ArgumentParser(description="Compuerta de reporte de FAW")
    p.add_argument("--reporte", type=Path, required=True,
                   help="Carpeta del proyecto de reporte (.Report)")
    p.add_argument("--modelo", type=Path, required=True, help="model.bim (JSON)")
    args = p.parse_args()

    if not args.reporte.exists() or not args.reporte.is_dir():
        print(f"ERROR: no existe la carpeta {args.reporte}", file=sys.stderr)
        return 2
    if not args.modelo.exists():
        print(f"ERROR: no existe {args.modelo}", file=sys.stderr)
        return 2

    try:
        modelo = json.loads(args.modelo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: modelo mal formado: {e}", file=sys.stderr)
        return 2

    jsons = list(args.reporte.rglob("*.json"))
    if not jsons:
        print(f"ERROR: no se encontro ningun .json bajo {args.reporte}", file=sys.stderr)
        return 2

    filtros: list[dict] = []
    campos_usados: set[str] = set()
    for jf in jsons:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # algunos archivos del proyecto no son JSON de contenido (metadata, etc.)
        rel = str(jf.relative_to(args.reporte)).replace("\\", "/")
        _buscar_filtros(data, rel, filtros)
        _buscar_campos(data, campos_usados)

    disponibles = campos_del_modelo(modelo)
    huerfanos = sorted(c for c in campos_usados if c not in disponibles)

    print(f"\n=== Reporte — {args.reporte.name} ===")
    print(f"  archivos JSON inspeccionados: {len(jsons)}")
    print(f"  campos/medidas referenciados (heuristica): {len(campos_usados)}")

    hay_problema = False

    if huerfanos:
        hay_problema = True
        print(f"\n  [ERROR] {len(huerfanos)} referencias que NO estan en el modelo "
              f"(revisar si son typos, campos renombrados, o falsos positivos de la heuristica):")
        for h in huerfanos[:20]:
            print(f"      {h}")
        if len(huerfanos) > 20:
            print(f"      ... y {len(huerfanos) - 20} mas")

    if filtros:
        print(f"\n  [AVISO] {len(filtros)} filtros persistidos encontrados — "
              f"revisar que ninguno sea un filtro de desarrollo olvidado:")
        for f in filtros[:15]:
            resumen = json.dumps(f["valor"])[:150]
            print(f"      {f['archivo']}  ({f['en']})")
            print(f"          {resumen}")
        if len(filtros) > 15:
            print(f"      ... y {len(filtros) - 15} mas")
        # Los filtros son un recibo para revisión humana, no reprueban solos.
    else:
        print("\n  filtros persistidos: ninguno encontrado")

    paso = not hay_problema
    print(f"\n  {'PASA' if paso else 'FALLA'}\n")

    detalle = (f"{len(jsons)} archivos, {len(campos_usados)} campos referenciados, "
              f"{len(huerfanos)} huerfanos, {len(filtros)} filtros para revisar")
    if paso:
        recibos.emitir("reporte", "verificar_reporte.py",
                       [args.modelo], detalle)
    else:
        recibos.invalidar("reporte")

    return 0 if paso else 1


if __name__ == "__main__":
    sys.exit(main())
