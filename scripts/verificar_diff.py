#!/usr/bin/env python3
"""
Compuerta `metadata` — inspecciona el diff completo y falla si toca metadata
protegida sin declararlo.

El bloque de metadata de un notebook vive al principio del archivo. Revisar un
diff mirando solo las lineas que cambiaron en el cuerpo, o un resumen tipo
"-50 +2", deja ese bloque fuera de cuadro: un commit puede aprobarse como
cambio "cosmetico" y perder el lakehouse por defecto sin que nadie lo note,
dejando el notebook sin poder ejecutarse. Esto lee el diff entero.

Es la compuerta mas fuerte del metodo: corre git localmente, no depende de que
nadie declare nada.

Uso
---
  python verificar_diff.py                        # working tree contra HEAD
  python verificar_diff.py --rango eaeadf0..HEAD  # entre dos commits
  python verificar_diff.py --permitir-metadata "cambio de lakehouse intencional"

Salida: 0 si pasa, 1 si toca metadata protegida sin permiso, 2 si git falla.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import recibos  # noqa: E402

# Claves de metadata cuya aparicion en un diff nunca es cosmetica.
# Perder cualquiera de estas rompe el artefacto en silencio.
PROTEGIDAS = [
    "default_lakehouse",
    "default_lakehouse_name",
    "default_lakehouse_workspace_id",
    "known_lakehouses",
    "dependencies",
    "environmentId",
    "environment",
    "workspaceId",
    "lakehouseId",
    "connectionId",
    "logicalId",
]

# Archivos cuya sola presencia en el diff es senal de metadata tocada, sin
# depender de que su contenido matchee una clave de PROTEGIDAS. Un reemplazo
# completo del archivo (o un formato de contenido que esta lista de claves no
# cubre) igual queda atrapado por el nombre. Mismos 4 archivos que AGENTS.md
# nombra como intocables.
ARCHIVOS_PROTEGIDOS = {
    ".platform",
    "lakehouse.metadata.json",
    "shortcuts.metadata.json",
    "alm.settings.json",
}

RE_CABECERA = re.compile(r"^(diff --git|index |--- |\+\+\+ |@@ )")

# La clave tiene que aparecer como clave de un objeto, no como substring de un
# comentario. Sin esto, un comentario que menciona "environment" daba falso
# positivo — lo detecto la revision critica.
RE_PROTEGIDAS = re.compile(
    r"""["']?\b(""" + "|".join(re.escape(k) for k in PROTEGIDAS) + r""")\b["']?\s*:"""
)


def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(["git"] + args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("ERROR: no se encontro git en el PATH", file=sys.stderr)
        sys.exit(2)
    if out.returncode != 0:
        print(f"ERROR: git {' '.join(args)} fallo:\n{out.stderr}", file=sys.stderr)
        sys.exit(2)
    return out.stdout


def obtener_diff(rango: str | None) -> str:
    if rango:
        return _git(["diff", rango])
    # Sin rango: todo lo que no esta en HEAD, staged y unstaged.
    return _git(["diff", "HEAD"])


def analizar(diff: str) -> tuple[dict[str, list[str]], int, int]:
    """Devuelve (hallazgos por archivo, lineas agregadas, lineas quitadas)."""
    hallazgos: dict[str, list[str]] = {}
    archivo = "(desconocido)"
    archivo_protegido_por_nombre = False
    tiene_cambio_de_contenido = False
    agregadas = quitadas = 0

    def _cerrar_archivo_anterior() -> None:
        # Un archivo protegido por nombre entra en hallazgos aunque ninguna
        # linea matchee PROTEGIDAS: un reemplazo completo o un formato de
        # contenido no cubierto por esa lista de claves no debe pasar gratis.
        if (archivo_protegido_por_nombre and tiene_cambio_de_contenido
                and archivo not in hallazgos):
            hallazgos[archivo] = ["(archivo protegido por nombre completo — "
                                   "cualquier cambio se trata como no cosmetico)"]

    for linea in diff.splitlines():
        if linea.startswith("diff --git"):
            _cerrar_archivo_anterior()
            partes = linea.split(" b/")
            archivo = partes[-1] if len(partes) > 1 else linea
            archivo_protegido_por_nombre = Path(archivo).name in ARCHIVOS_PROTEGIDOS
            tiene_cambio_de_contenido = False
            continue
        if RE_CABECERA.match(linea):
            continue

        if linea.startswith("+"):
            agregadas += 1
        elif linea.startswith("-"):
            quitadas += 1
        else:
            continue

        tiene_cambio_de_contenido = True

        if RE_PROTEGIDAS.search(linea):
            hallazgos.setdefault(archivo, []).append(linea.rstrip())

    _cerrar_archivo_anterior()
    return hallazgos, agregadas, quitadas


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Compuerta de metadata de FAW")
    p.add_argument("--rango", help="rango de commits, ej. abc123..HEAD")
    p.add_argument("--permitir-metadata", metavar="MOTIVO",
                   help="declara que el cambio de metadata es intencional")
    args = p.parse_args()

    ambito = args.rango or "working tree contra HEAD"
    diff = obtener_diff(args.rango)
    if not diff.strip():
        print("\n  Sin cambios que inspeccionar.\n  PASA\n")
        recibos.emitir("metadata", "verificar_diff.py", [],
                       f"{ambito}: sin cambios")
        return 0

    hallazgos, agregadas, quitadas = analizar(diff)

    print(f"\n=== Metadata — {args.rango or 'working tree contra HEAD'} ===")
    print(f"  lineas: +{agregadas} -{quitadas}")

    if not hallazgos:
        print("  metadata protegida: sin cambios")
        print("\n  PASA\n")
        recibos.emitir("metadata", "verificar_diff.py", [],
                       f"{ambito}: +{agregadas} -{quitadas}, metadata intacta")
        return 0

    total = sum(len(v) for v in hallazgos.values())
    print(f"  metadata protegida: {total} lineas en {len(hallazgos)} archivos\n")
    for archivo, lineas in hallazgos.items():
        print(f"  {archivo}")
        for l in lineas[:12]:
            print(f"      {l[:120]}")
        if len(lineas) > 12:
            print(f"      ... y {len(lineas) - 12} mas")
        print()

    if args.permitir_metadata:
        print(f"  Declarado intencional: {args.permitir_metadata}")
        print("\n  PASA (con declaracion)\n")
        # El bypass queda EN el recibo: si alguien mira despues por que paso una
        # compuerta de metadata con cambios, encuentra el motivo y quien lo puso.
        recibos.emitir("metadata", "verificar_diff.py --permitir-metadata", [],
                       f"{ambito}: {total} lineas de metadata en "
                       f"{len(hallazgos)} archivos, DECLARADO INTENCIONAL: "
                       f"{args.permitir_metadata}")
        return 0

    print("  Este diff NO es cosmetico: toca metadata que hace funcionar al artefacto.")
    print("  Si el cambio es intencional, volve a correr con:")
    print('      --permitir-metadata "motivo"')
    print("\n  FALLA\n")
    recibos.invalidar("metadata")
    return 1


if __name__ == "__main__":
    sys.exit(main())
