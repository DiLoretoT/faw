#!/usr/bin/env python3
"""
Hook PreToolUse de Claude Code — hace que la compuerta `metadata` sea una
restriccion real, no una convencion.

Se dispara antes de CUALQUIER llamada a la herramienta Bash o PowerShell.
Si el comando es un `git commit`, corre verificar_diff.py sobre el diff que
esta por comitearse. Si encuentra metadata protegida sin declarar, BLOQUEA
la llamada (exit 2) antes de que el commit exista.

Formato de entrada/salida verificado contra la doc oficial de Claude Code
(code.claude.com/docs/en/hooks, leida el 2026-08-01):
  - stdin: JSON con tool_name, tool_input.command, cwd.
  - exit 0  -> permite.
  - exit 2  -> bloquea; stderr se le muestra a Claude como motivo.
  - cualquier otro exit -> no bloqueante (se registra pero no impide).

No reemplaza el chequeo manual de verificar_diff.py: lo hace imposible de
saltear por olvido. Sigue sin poder inspeccionar Livy (codigo Spark arbitrario,
fuera del alcance de este hook) — ver GUIA_COMPLETA.md, seccion "Lo que no se
puede bloquear".
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import superficie  # noqa: E402

FAW_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFICADOR = FAW_ROOT / "scripts" / "verificar_diff.py"
VERIF_PLATAFORMA = FAW_ROOT / "scripts" / "verificar_plataforma.py"

RE_GIT_COMMIT = re.compile(r"\bgit\s+(?:-[A-Za-z-]+(?:=\S+)?\s+)*commit\b")


def _permitido_por_override(repo: Path, nombre: str) -> str | None:
    """
    Archivo de un solo uso: si el agente decidio a proposito que el cambio es
    intencional, lo declara ahi ANTES de comitear. Se borra al consumirse, para
    que no quede como un bypass permanente y silencioso.
    """
    f = repo / ".faw" / nombre
    if not f.exists():
        return None
    motivo = f.read_text(encoding="utf-8-sig").strip()  # -sig: tolera el BOM que agrega PowerShell
    if not motivo:
        return None
    f.unlink()
    return motivo


def main() -> int:
    try:
        # Leido como bytes y decodificado explicito a UTF-8: en Windows,
        # sys.stdin.read() por defecto usa cp1252 y puede romper con
        # caracteres que Claude Code manda en UTF-8.
        crudo = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        entrada = json.loads(crudo)
    except json.JSONDecodeError:
        # No se puede leer la entrada: fallar ABIERTO. Bloquear todos los
        # commits por un error de parseo del hook seria un fallo peor que el
        # que se intenta prevenir.
        return 0

    comando = (entrada.get("tool_input") or {}).get("command", "") or ""
    if not RE_GIT_COMMIT.search(comando):
        return 0  # no es un commit, no nos incumbe

    repo = Path(entrada.get("cwd") or ".")

    if not VERIFICADOR.exists():
        print(f"[faw-hook] no se encontro {VERIFICADOR} — no se pudo verificar, "
              f"se permite el commit sin chequeo", file=sys.stderr)
        return 0

    resultado = subprocess.run(
        [sys.executable, str(VERIFICADOR)],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )

    # OJO: aca no se retorna temprano. La primera version de esta extension hacia
    # `return 0` cuando metadata pasaba, y la compuerta de plataforma quedaba
    # INALCANZABLE en el caso normal (diff sin metadata protegida). Se descubrio
    # porque la prueba del hook no bloqueo un literal inventado — probando, no
    # leyendo. Las dos compuertas son independientes: las dos corren siempre.
    if resultado.returncode == 2:
        # Error del propio script (repo invalido, etc.) — fallar abierto en esta
        # compuerta, pero la de plataforma corre igual.
        print(f"[faw-hook] verificar_diff.py fallo al ejecutar:\n{resultado.stderr}\n"
              f"Se permite el chequeo de metadata; revisar el hook.", file=sys.stderr)

    if resultado.returncode == 1:
        # Encontro metadata protegida sin declarar.
        motivo = _permitido_por_override(repo, "metadata-permitida.txt")
        if motivo:
            print(f"[faw-hook] metadata protegida detectada, pero declarada intencional: "
                  f"{motivo}", file=sys.stderr)
        else:
            print(
                "[faw-hook] COMMIT BLOQUEADO — este diff toca metadata protegida "
                "(default_lakehouse, dependencies, environment, ...) sin declararlo.\n\n"
                + resultado.stdout + "\n"
                "Si el cambio es intencional:\n"
                "  1. Correr:  python " + str(VERIFICADOR) + ' --permitir-metadata "motivo"\n'
                "  2. O escribir el motivo en .faw/metadata-permitida.txt del repo y reintentar "
                "el commit (el archivo se borra solo al usarse).\n"
                "     OJO: este hook es PreToolUse, corre ANTES del comando. Escribir el archivo\n"
                "     y comitear en la MISMA llamada no funciona: cuando el hook mira, todavia no\n"
                "     existe. Van en dos pasos.\n",
                file=sys.stderr,
            )
            return 2

    codigo = _verificar_plataforma(repo)
    if codigo != 0:
        return codigo
    return _verificar_superficie(repo)


def _verificar_superficie(repo: Path) -> int:
    """
    Compuerta `superficie` sobre el diff staged: el checklist de `cliente.md`
    aplicado a los ARCHIVOS, no al cuerpo del PR.

    Revisar el cuerpo del PR no alcanza: el contenido que llega a superficie de
    cliente esta en los archivos, no en el resumen del cambio. Esta compuerta
    revisa el diff staged. Aplica a todo repo gobernado: FAW no distingue repos
    propios de repos de cliente.
    """
    hallazgos = superficie.revisar_diff_staged(repo)
    if not hallazgos:
        return 0

    motivo = _permitido_por_override(repo, "superficie-permitida.txt")
    if motivo:
        print(f"[faw-hook] superficie de cliente: {len(hallazgos)} hallazgos, "
              f"declarados intencionales: {motivo}", file=sys.stderr)
        return 0

    detalle = "\n".join(
        f"  {archivo}:{nro}\n      {motivo_h}\n      -> \"{frag[:70]}\""
        for archivo, nro, motivo_h, frag in hallazgos[:12]
    )
    resto = f"\n  ... y {len(hallazgos) - 12} mas" if len(hallazgos) > 12 else ""

    print(
        "[faw-hook] COMMIT BLOQUEADO — el diff agrega contenido que no corresponde a "
        "un repo que lee un tercero (FAW trata todo repo gobernado como superficie de "
        "cliente).\n\n"
        + detalle + resto + "\n\n"
        "Lo que va en un repo de cliente es qué cambió y cómo se validó. El razonamiento "
        "de diseño, los hallazgos abiertos, las preguntas de negocio, los nombres de "
        "personas con tareas asignadas y las referencias a metodología o repos internos "
        "van al tracker interno del proyecto (reglas/cliente.md).\n"
        "Si es un falso positivo, escribir el motivo en .faw/superficie-permitida.txt y "
        "reintentar. OJO: el hook es PreToolUse, corre ANTES del comando — escribir el "
        "archivo y comitear en la MISMA llamada no funciona, el archivo todavia no existe. "
        "Van en dos pasos.\n",
        file=sys.stderr,
    )
    return 2


def _verificar_plataforma(repo: Path) -> int:
    """
    Compuerta `plataforma` en el mismo momento: sobre el diff staged, antes de
    que el commit exista. El principio 6 ya prohibe inventar literales de
    plataforma por analogia. Esta compuerta lo hace cumplir en el momento de
    escribir, no despues.
    """
    if not VERIF_PLATAFORMA.exists():
        print(f"[faw-hook] no se encontro {VERIF_PLATAFORMA} — se permite el commit "
              f"sin chequeo de plataforma", file=sys.stderr)
        return 0

    resultado = subprocess.run(
        [sys.executable, str(VERIF_PLATAFORMA)],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )

    if resultado.returncode == 0:
        return 0
    if resultado.returncode != 1:
        # Error del propio script — fallar abierto, avisando.
        print(f"[faw-hook] verificar_plataforma.py fallo al ejecutar:\n{resultado.stderr}\n"
              f"Se permite el commit; revisar el hook.", file=sys.stderr)
        return 0

    motivo = _permitido_por_override(repo, "plataforma-permitida.txt")
    if motivo:
        print(f"[faw-hook] literal de plataforma sin verificar, pero declarado "
              f"intencional: {motivo}", file=sys.stderr)
        return 0

    print(
        "[faw-hook] COMMIT BLOQUEADO — el diff contiene literales de plataforma de "
        "Microsoft ($schema, connection string) sin precedente en el repo y que no "
        "resuelven.\n\n" + resultado.stdout + "\n"
        "Un literal inventado por analogia puede romper en la pantalla del "
        "usuario final. Copiarlo de un artefacto real, dejar que la herramienta "
        "lo genere, o leer la doc oficial. Si es un caso legitimo (ej. sin red), "
        "escribir el motivo en .faw/plataforma-permitida.txt y reintentar.\n"
        "OJO: hook PreToolUse — escribir el archivo y comitear en la misma llamada no\n"
        "funciona, corre antes del comando. Van en dos pasos.\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
