#!/usr/bin/env python3
"""
Hook UserPromptSubmit de Claude Code — pone el metodo delante del modelo en
CADA turno, sin depender de que el agente se acuerde de ir a leerlo.

Por que este evento y no SessionStart: `UserPromptSubmit` corre antes de que
Claude procese cada mensaje, asi que el estado sigue presente despues de una
compactacion y despues de un /clear. SessionStart corre una sola vez: no cubre
reanudar despues de esos puntos, y ahi el metodo puede estar escrito sin que el
agente se entere de que existe.

Formato verificado contra la doc oficial de Claude Code
(code.claude.com/docs/en/hooks, leida el 2026-08-04):
  - Solo UserPromptSubmit, UserPromptExpansion y SessionStart tienen su stdout
    agregado al contexto que Claude ve.
  - La forma estructurada es
    {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                            "additionalContext": "..."}}
  - JSON en stdout se procesa solo con exit 0.

REGLA DE DISENO: la inyeccion tiene que ser CORTA. Corre en cada turno, y un
hook que narra en cada turno entrena a dejar de leerlo. Se inyecta el estado,
la regla de la fase actual, y nada mas.

Opt-in: no hace nada salvo que el proyecto tenga un directorio `.faw/`. FAW
instalado global no mete contexto de Fabric en un proyecto de Next.js.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FAW_ROOT = Path(__file__).resolve().parent.parent.parent
TRANSICIONES = FAW_ROOT / "faw" / "transiciones.json"

# Sin emoji a proposito: en Windows stdout usa cp1252 por default y un caracter
# fuera de ese set hace crashear el hook. Un hook que crashea sale con codigo != 0,
# que la doc trata como NO bloqueante — o sea que FAW quedaria "instalado" sin
# hacer cumplir nada, en silencio. Se reconfigura stdout a UTF-8 abajo igual,
# porque el titulo del ticket viene del estado y puede traer acentos.
LINEA_ESTADO = (
    "Toda respuesta arranca con una linea de estado: `[consulta]` para una pregunta suelta, "
    "o `{TIER} - {accion} | {ticket}: {titulo}` cuando hay trabajo abierto."
)

# Skill oficial de Microsoft que gobierna la mecanica, por tier. FAW manda en
# proceso; estas mandan en como se hace el artefacto. Ver reglas/skills-microsoft.md.
SKILL_MS_POR_TIER = {
    "REPORTE": "powerbi-report-planning (si el reporte es nuevo) y despues powerbi-report-authoring",
    "MODELO": "semantic-model-authoring",
}

REGLA_POR_FASE = {
    "CLASIFICACION": "Reformular el pedido, mirar el estado real, asignar tier, definir que NO entra. "
                "No construir nada todavia. Cierra con confirmacion del usuario.",
    "PERFILADO": "Solo lectura. Cada numero va con la consulta que lo produjo. "
                 "La clave natural se prueba, no se copia de una ficha.",
    "DISENO": "Grano en una frase, clave natural verificada, contrato .yml. "
              "Cierra con confirmacion del usuario ANTES de construir.",
    "CONSTRUCCION": "PASO 0: si el artefacto tiene skill oficial de Microsoft, leerla ANTES de "
                    "escribir una linea. Validaciones adentro del artefacto. Reportar filas Y columnas.",
    "VALIDACION": "La ejecuta faw-validador, que no construyo. Busca refutar, no confirmar. "
                  "Si falla, vuelve a CONSTRUCCION: no se parchea aca.",
    "PUBLICACION": "Verificar el diff COMPLETO. Leer reglas/cliente.md antes de escribir "
                   "el PR. Actualizar el tracker con el punto de retomada.",
}


def _estado(repo: Path) -> dict | None:
    """Ultima entrada de la maquina de estados, o None si no hay trabajo abierto."""
    f = repo / ".faw" / "estado.jsonl"
    if not f.exists():
        return None
    ultima = None
    for linea in f.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            ultima = json.loads(linea)
        except json.JSONDecodeError:
            continue
    return ultima


def _salidas(tier: str, fase: str) -> str:
    """Transiciones legales desde donde estamos, con sus compuertas."""
    try:
        g = json.loads(TRANSICIONES.read_text(encoding="utf-8"))
    except Exception:
        return ""
    aristas = (g.get("tiers", {}).get(tier) or {})
    partes = []
    for arista, cfg in aristas.items():
        if not isinstance(cfg, dict) or "->" not in arista:
            continue
        origen, destino = arista.split("->", 1)
        if origen != fase:
            continue
        compuertas = cfg.get("compuertas") or []
        partes.append(f"{destino}" + (f" (compuertas: {', '.join(compuertas)})" if compuertas else ""))
    return " | ".join(partes)


def main() -> int:
    # En Windows stdout es cp1252 por default: cualquier caracter fuera de ese set
    # (un acento en el titulo del ticket, un emoji) hace crashear el hook, y un
    # hook que crashea NO bloquea — FAW quedaria instalado sin hacer cumplir nada.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        crudo = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        entrada = json.loads(crudo)
    except json.JSONDecodeError:
        return 0  # sin entrada legible no hay nada que inyectar; fallar abierto

    repo = Path(entrada.get("cwd") or ".")

    # --- Opt-in ---------------------------------------------------------------
    if not (repo / ".faw").is_dir():
        return 0

    st = _estado(repo)
    fase = (st or {}).get("fase") or (st or {}).get("phase")
    tier = (st or {}).get("tier")
    ticket = (st or {}).get("ticket")
    titulo = (st or {}).get("titulo") or (st or {}).get("title") or ""

    lineas = []

    if not st or fase in (None, "IDLE"):
        lineas += [
            "[FAW] Sin trabajo clasificado.",
            "Antes del primer Write/Edit hay que clasificar: clasificar tier, definir que entra y "
            "que NO, y esperar tu OK. La skill es /faw:faw-clasificar. El hook de escritura va a "
            "denegar cualquier edicion hasta que exista la clasificación.",
            LINEA_ESTADO,
        ]
    else:
        lineas.append(f"[FAW] {tier} - {fase} | {ticket}: {titulo}")
        regla = REGLA_POR_FASE.get(fase)
        if regla:
            lineas.append(f"Fase {fase}: {regla}")
        skill = SKILL_MS_POR_TIER.get(tier or "")
        if skill and fase == "CONSTRUCCION":
            lineas.append(f"Skill oficial de Microsoft para este tier: {skill}.")
        salidas = _salidas(tier or "", fase)
        if salidas:
            lineas.append(f"Salidas legales: {salidas}")
        lineas.append(LINEA_ESTADO)

    contexto = "\n".join(lineas)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": contexto,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
