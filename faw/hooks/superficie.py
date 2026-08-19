#!/usr/bin/env python3
"""
Modulo compartido: el checklist de `reglas/cliente.md` como codigo, en un solo lugar.

## Por que existe

Los patrones vivian dentro de `compuerta_pr.py` y solo se aplicaban al **cuerpo
de un PR**. Revisar solo el cuerpo del PR revisa el resumen del trabajo, no el
trabajo: el mismo contenido que una compuerta asi rechaza puede seguir
publicado en el repo del cliente por otra via, en los archivos comiteados —
por ejemplo un texto marcado como interno, visible en un artefacto del reporte,
dentro del tenant del cliente, sin que nada lo revise.

Hay tambien formas de pasar el cuerpo de un PR que no se pueden leer como un
string simple — un heredoc con `--body-file -`, por ejemplo — y que tienen que
quedar cubiertas igual que un `--body` literal.

Este modulo centraliza los patrones para que los apliquen las dos compuertas:
la del PR y la del commit.

El checklist aplica a TODO repo gobernado por FAW. No hay distincion entre
repos propios y repos de cliente: se escribe siempre como si el destinatario
del repo fuera a leerlo. Lo especifico de cada proyecto (nombres de personas,
literales internos) se declara en `.faw/config.json`, que no se versiona.

## Falsos positivos, a proposito

`\bdel cliente\b` matchea tambien un uso de negocio legitimo ("el codigo del
cliente" en un `dim_cliente`). Se prefiere frenar y que el motivo se declare en
el archivo de override antes que dejar pasar la frase que ya se publico. `clientes`
en plural y `dim_cliente` no matchean.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# Claves de `.faw/config.json`. Las dos son listas, vacias por defecto: lo que
# cada proyecto no quiere que se filtre lo declara el usuario, no el codigo.
CLAVE_PERSONAS = "personas_cliente"
CLAVE_LITERALES = "literales_internos"

# (regex, que decir). Cada patron responde a un modo de fallo observado, no imaginado.
PROHIBIDO: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bclaude\b|\bcopilot\b|\banthropic\b|generated with|"
                r"co-authored-by:\s*claude", re.IGNORECASE),
     "atribucion de IA — prohibida en un repo de cliente, sin excepcion"),
    (re.compile(r"\bFAW\b|faw-clasificar|faw-encuadrar|compuerta[s]?\s+de\s+FAW"),
     "el metodo interno de trabajo no va en un repo de cliente"),
    (re.compile(r"\b(al|el|del|para el|con el) cliente\b", re.IGNORECASE),
     "habla del cliente en tercera persona, en su propio repo"),
    (re.compile(r"no mostrar\b|no compartir\b|uso interno|\binterno:", re.IGNORECASE),
     "nota de trabajo marcada como interna, escrita en un artefacto que el cliente lee"),
    (re.compile(r"pregunta abierta|hallazgo para el tracker|llevar a \w+|"
                r"conviene explicarle|coordinar con \w+|confirmar con \w+", re.IGNORECASE),
     "hallazgo abierto o tarea asignada a alguien del cliente — va al tracker interno"),
]


def _config(repo: Path) -> dict:
    """`.faw/config.json` del proyecto. No se versiona, asi que puede no existir."""
    f = repo / ".faw" / "config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}


def patrones(repo: Path) -> list[tuple[re.Pattern[str], str]]:
    """PROHIBIDO + lo que declare `.faw/config.json`: personas y literales internos."""
    ps = list(PROHIBIDO)
    cfg = _config(repo)
    nombres = [re.escape(str(p).strip())
               for p in (cfg.get(CLAVE_PERSONAS) or [])
               if str(p).strip()]
    if nombres:
        ps.append((
            re.compile(r"\b(" + "|".join(nombres) + r")\b", re.IGNORECASE),
            "nombra a una persona del cliente — los nombres, y las tareas que se les "
            "asignan, van al tracker interno",
        ))
    literales = [re.escape(str(lit).strip())
                 for lit in (cfg.get(CLAVE_LITERALES) or [])
                 if str(lit).strip()]
    if literales:
        ps.append((
            re.compile("|".join(literales), re.IGNORECASE),
            "literal declarado como interno en .faw/config.json — nombres de otros "
            "proyectos, repos o metodologia propia no van en un repo publicado",
        ))
    return ps


def revisar(texto: str, repo: Path) -> list[tuple[str, str]]:
    """[(motivo, fragmento)] por cada patron que matchea. Lista vacia = pasa."""
    hallazgos = []
    for rx, motivo in patrones(repo):
        m = rx.search(texto)
        if m:
            hallazgos.append((motivo, m.group(0)))
    return hallazgos


def lineas_agregadas(repo: Path) -> list[tuple[str, int, str]]:
    """
    Lineas que el commit AGREGA, del diff staged. Devuelve (archivo, nro, texto).

    Solo lineas agregadas: lo que ya estaba se corrige aparte, no bloqueando cada
    commit que lo roce.

    Quedan fuera del chequeo `.faw/` (que no se versiona) y `docs/faw/`, que son
    artefactos del propio metodo. La excepcion a la excepcion es
    `docs/faw/tickets/`, que SI se revisa: un ticket contiene por naturaleza
    preguntas abiertas y tareas asignadas a personas, que es exactamente el
    contenido que no debe llegar a un repo que lee un tercero. Eximirlo por vivir
    bajo `docs/faw/` seria abrir la puerta mas ancha justo donde pasa el material
    mas sensible.
    """
    try:
        r = subprocess.run(["git", "diff", "--cached", "--unified=0", "--no-color"],
                           cwd=str(repo), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []

    salida: list[tuple[str, int, str]] = []
    archivo = ""
    nro = 0
    for linea in r.stdout.splitlines():
        if linea.startswith("+++ b/"):
            archivo = linea[6:]
            continue
        if linea.startswith("@@"):
            m = re.search(r"\+(\d+)", linea)
            nro = int(m.group(1)) if m else 0
            continue
        if linea.startswith("+") and not linea.startswith("+++"):
            exento = (archivo.startswith((".faw/", "docs/faw/"))
                      and not archivo.startswith("docs/faw/tickets/"))
            if archivo and archivo != "/dev/null" and not exento:
                salida.append((archivo, nro, linea[1:]))
            nro += 1
    return salida


def revisar_diff_staged(repo: Path) -> list[tuple[str, int, str, str]]:
    """
    Aplica los patrones a las lineas que el commit agrega.
    Devuelve (archivo, nro, motivo, fragmento). Lista vacia = pasa.
    """
    ps = patrones(repo)
    hallazgos = []
    for archivo, nro, texto in lineas_agregadas(repo):
        for rx, motivo in ps:
            m = rx.search(texto)
            if m:
                hallazgos.append((archivo, nro, motivo, m.group(0)))
                break
    return hallazgos
