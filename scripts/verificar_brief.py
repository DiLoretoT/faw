#!/usr/bin/env python3
"""
Compuerta `brief` — sin ella, "construccion libre" en el tier REPORTE se lee
como "no hace falta preguntar nada": el agente puede terminar deduciendo el
alcance leyendo el modelo semantico en vez de acordar con el usuario objetivo,
audiencia y que preguntas tiene que responder el reporte.

El tier REPORTE tenia `CLASIFICACION->CONSTRUCCION` con `compuertas: []`. La
skill oficial de Microsoft para esto (`powerbi-report-planning`) exige justo lo
contrario para un reporte nuevo: Define -> Inspect -> Spec -> **Approve** ->
Build. FAW declara a esas skills como autoridad en mecanica; dejar la entrada
sin compuerta las contradecia.

Por que es de fuerza `maquina` y no `recibo`: un recibo solo comprueba que el
archivo exista y pese mas de 200 bytes. Eso lo satisface un archivo con el
template sin llenar. Este script verifica que cada seccion tenga contenido real
y que no queden marcadores del template.

Uso
---
  python verificar_brief.py --ticket <TICKET>
  python verificar_brief.py --brief docs/faw/<TICKET>/brief.md

Salida: 0 si el brief esta completo (y emite el recibo), 1 si falta algo,
2 si los insumos estan mal.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import recibos  # noqa: E402

# Cada seccion con el minimo de contenido util que se le exige, en caracteres.
# No son numeros arbitrarios: "Contabilidad" (12) no es una audiencia, y
# "ver saldos" (10) no es un objetivo.
SECCIONES = {
    "objetivo": 60,
    "audiencia": 40,
    "preguntas": 80,
    "fuera de alcance": 30,
    "origen de datos": 30,
}

# Marcadores que deja el template. Si sobreviven, el brief no se lleno.
#
# DOTALL y sin tope de 60 caracteres a proposito: la primera version usaba
# `<[^<>\n]{3,60}>` y el template SIN LLENAR pasaba la compuerta casi entera —
# sus placeholders son parrafos de varias lineas, no cabian en el tope, no
# matcheaban, y su largo contaba como contenido real. Se descubrio probando,
# no leyendo. Es el mismo patron que la compuerta viene a atrapar: algo que
# parece verificado y no lo esta.
RE_PLACEHOLDER = re.compile(
    r"<[^<>]{3,600}>|\bTODO\b|\bXXX\b|\bcompletar\b",
    re.IGNORECASE | re.DOTALL,
)

# Una pregunta de negocio termina en signo de interrogacion. Se exigen 3: con
# menos de tres no hay un reporte, hay un visual.
MIN_PREGUNTAS = 3


def _secciones(texto: str) -> dict[str, str]:
    """Parte el markdown por encabezados y devuelve {titulo normalizado: cuerpo}."""
    out: dict[str, str] = {}
    actual = None
    buf: list[str] = []
    for linea in texto.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", linea)
        if m:
            if actual is not None:
                out[actual] = "\n".join(buf).strip()
            titulo = m.group(1).strip().lower()
            titulo = re.sub(r"^\d+[\.\)]\s*", "", titulo)          # "1. Objetivo" -> "objetivo"
            titulo = titulo.replace("á", "a").replace("é", "e").replace("í", "i")
            titulo = titulo.replace("ó", "o").replace("ú", "u")
            actual = titulo
            buf = []
        elif actual is not None:
            buf.append(linea)
    if actual is not None:
        out[actual] = "\n".join(buf).strip()
    return out


def _match_seccion(secciones: dict[str, str], clave: str) -> tuple[str, str] | None:
    for titulo, cuerpo in secciones.items():
        if clave in titulo:
            return titulo, cuerpo
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Compuerta de brief de FAW (tier REPORTE)")
    p.add_argument("--ticket", help="Ticket; busca docs/faw/<ticket>/brief.md")
    p.add_argument("--brief", type=Path, help="Ruta explicita al brief")
    a = p.parse_args()

    if a.brief:
        ruta = a.brief
    elif a.ticket:
        ruta = Path("docs") / "faw" / a.ticket / "brief.md"
    else:
        print("ERROR: hace falta --ticket o --brief", file=sys.stderr)
        return 2

    print(f"\n=== Brief — {ruta} ===")

    if not ruta.exists():
        print(f"\n  [ERROR] no existe {ruta}.\n"
              f"  Antes de construir un reporte hay que acordar con el usuario para que existe.\n"
              f"  Plantilla: faw/contratos/PLANTILLA.brief.md\n\n  FALLA\n")
        recibos.invalidar("brief")
        return 1

    texto = ruta.read_text(encoding="utf-8", errors="replace")
    secciones = _secciones(texto)
    fallos: list[str] = []

    for clave, minimo in SECCIONES.items():
        hallado = _match_seccion(secciones, clave)
        if hallado is None:
            fallos.append(f"falta la seccion '{clave}'")
            continue
        titulo, cuerpo = hallado
        # Se descuentan los marcadores del template antes de medir, para que un
        # brief lleno de "<completar>" no pase por tener muchos caracteres.
        limpio = RE_PLACEHOLDER.sub("", cuerpo).strip()
        if len(limpio) < minimo:
            fallos.append(f"'{titulo}' tiene {len(limpio)} caracteres utiles, "
                          f"se esperan al menos {minimo}")
        if RE_PLACEHOLDER.search(cuerpo):
            fallos.append(f"'{titulo}' todavia tiene marcadores del template sin llenar")

    preg = _match_seccion(secciones, "preguntas")
    if preg:
        n = preg[1].count("?")
        if n < MIN_PREGUNTAS:
            fallos.append(f"'preguntas' declara {n} preguntas y se exigen {MIN_PREGUNTAS} "
                          f"(cada una termina en '?')")

    print(f"  secciones encontradas: {len(secciones)}")

    if fallos:
        print(f"\n  [ERROR] el brief esta incompleto:")
        for f in fallos:
            print(f"      {f}")
        print("\n  Esto no se completa solo: son preguntas para el usuario.\n\n  FALLA\n")
        recibos.invalidar("brief")
        return 1

    print("\n  PASA\n")
    recibos.emitir("brief", "verificar_brief.py", [ruta],
                   f"brief completo en {ruta} ({len(secciones)} secciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
