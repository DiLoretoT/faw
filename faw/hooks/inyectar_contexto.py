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

# Que skill oficial de la plataforma gobierna la mecanica de cada tipo de
# artefacto. Se nombra el tema y no la ruta: el repositorio de Microsoft
# reorganiza sus carpetas entre versiones, y una ruta escrita aca mandaria a leer
# un archivo que ya no existe. FAW manda en proceso; esas skills en mecanica.
SKILL_MS_POR_ARTEFACTO = {
    "notebook": "la skill de Spark",
    "lakehouse": "la skill de Spark",
    "tabla": "la skill de Spark",
    "modelo-semantico": "la skill de autoria de modelo semantico",
    "reporte": "las skills de planificacion y autoria de reportes",
    "pipeline": "la skill de pipelines de datos",
    "dataflow": "la skill de dataflows",
    "warehouse": "la skill de warehouse",
}

# Sin `--artefacto` declarado se cae al tier, que es menos preciso pero cubre los
# dos casos donde el tier ya identifica el artefacto.
SKILL_MS_POR_TIER = {
    "REPORTE": "las skills de planificacion y autoria de reportes",
    "MODELO": "la skill de autoria de modelo semantico",
}

REGLA_POR_FASE = {
    "CLASIFICACION": "Reformular el pedido, mirar el estado real, asignar tier, definir que NO entra. "
                "No construir nada todavia. Cierra con confirmacion del usuario.",
    "PERFILADO": "Solo lectura. Cada numero va con la consulta que lo produjo. "
                 "La clave natural se prueba, no se copia de una ficha.",
    "DISENO": "Grano en una frase, clave natural verificada, contrato .yml. Antes de cerrar, "
              "revisar que decisiones de arquitectura quedan implicitas en lo que se va a "
              "construir y proponerlas al usuario: las que no se discuten las decide el default "
              "de la herramienta. Cierra con confirmacion del usuario ANTES de construir.",
    "CONSTRUCCION": "PASO 0: si el artefacto tiene skill oficial de Microsoft, leerla ANTES de "
                    "escribir una linea. Validaciones adentro del artefacto. Reportar filas Y columnas.",
    "VALIDACION": "La ejecuta faw-validador, que no construyo. Busca refutar, no confirmar. "
                  "Si falla, vuelve a CONSTRUCCION: no se parchea aca.",
    "PUBLICACION": "Verificar el diff COMPLETO. Leer reglas/cliente.md antes de escribir "
                   "el PR. Actualizar el tracker con el punto de retomada.",
}


def _estado(repo: Path) -> dict | None:
    """Estado vigente del trabajo abierto, o None si no hay ninguno.

    El archivo es un log de eventos: la fase vigente esta en la ultima linea, pero
    lo que se declaro al abrir el trabajo —el tipo de artefacto, el documento de
    contexto previo— solo esta en la linea del `iniciar`. Leer unicamente la
    ultima entrada hace que esos datos existan durante la primera fase y
    desaparezcan en cuanto se avanza, que es peor que no tenerlos: se declaran una
    vez y dejan de aplicarse sin que nadie lo note.

    Por eso se combina la ultima entrada con la del `iniciar` del mismo ticket,
    en vez de exigir que cada transicion arrastre todos los campos.
    """
    f = repo / ".faw" / "estado.jsonl"
    if not f.exists():
        return None

    entradas = []
    for linea in f.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            entradas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    if not entradas:
        return None

    ultima = entradas[-1]
    ticket = ultima.get("ticket")
    for e in reversed(entradas):
        if e.get("evento") == "iniciar" and e.get("ticket") == ticket:
            combinado = dict(e)
            combinado.update({k: v for k, v in ultima.items() if v is not None})
            return combinado
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

        # El documento de una consulta previa ya tiene decisiones cerradas con el
        # usuario. Se nombra la ruta y no se vuelca el contenido: el punto es que
        # el agente lo lea en vez de volver a preguntar lo que ya se contesto.
        contexto_previo = (st or {}).get("contexto")
        if contexto_previo:
            lineas.append(f"Contexto ya acordado con el usuario en {contexto_previo}: "
                          f"leerlo antes de preguntar nada que pueda estar ahi.")

        artefacto = (st or {}).get("artefacto")
        skill = (SKILL_MS_POR_ARTEFACTO.get((artefacto or "").lower())
                 or SKILL_MS_POR_TIER.get(tier or ""))
        if skill and fase in ("DISENO", "CONSTRUCCION"):
            lineas.append(f"Mecanica de plataforma: leer {skill} del repositorio oficial "
                          f"antes de escribir.")
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
