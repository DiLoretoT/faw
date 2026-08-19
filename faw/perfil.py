#!/usr/bin/env python3
"""
Perfil del proyecto: lo que FAW no puede saber solo y no debe suponer.

## El problema

Un metodo de trabajo sobre una plataforma de datos toca infraestructura que
cambia de una instalacion a otra: donde viven los tickets, si existe un ambiente
de desarrollo separado del productivo, si se puede ejecutar codigo contra el
tenant. Escribir esas respuestas dentro del metodo lo vuelve util para un
proyecto e incorrecto para el resto.

## Dos archivos, porque son dos cosas distintas

`faw.json`, en la raiz del repo de trabajo, **se versiona**. Contiene las reglas
de proceso del proyecto: que gestor de tickets se usa, si hay un ambiente de
desarrollo, como se promueve a produccion. Son decisiones del equipo, no de la
maquina de quien las escribio: tienen que viajar con el repo, revisarse en un PR
y ser iguales para todos. Un perfil que vive solo en una maquina produce dos
personas trabajando bajo reglas distintas sin que nada lo detecte.

`.faw/config.json`, que **no se versiona**, contiene lo que no puede publicarse
ni compartirse: nombres de personas, literales internos, rutas locales. Mezclar
ambos obliga a elegir entre publicar nombres o esconder reglas.

## Como se resuelve la ausencia de datos

Por la opcion que mas control pide, nunca por la que mas permite. Sin declaracion
de ambientes se asume uno solo, y uno solo es productivo. La asimetria lo
justifica: un valor estricto de mas cuesta una autorizacion que el usuario iba a
dar igual; uno permisivo de mas escribe en produccion sin preguntar.

Ese default no es una hipotesis pesimista. Microsoft documenta el despliegue en
un unico workspace como patron valido y soportado para organizaciones chicas, y
en ese patron los Deployment Pipelines no existen porque requieren varios
workspaces. Un proyecto sin ambiente de desarrollo es un caso normal, no una
instalacion mal hecha.

## Un valor declarado tiene consecuencia, o no se declara

Cada clave de este archivo cambia algo que el metodo hace. `ambientes.dev`
decide si una escritura contra el tenant exige que la autorizacion quede por
escrito antes de ejecutarse. `tickets.sistema` decide de donde sale el
identificador del trabajo y si hay un backlog externo que consultar. Una clave
que solo produjera texto distinto no estaria aca.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Perfil de proceso, versionado con el repo de trabajo.
ARCHIVO_PERFIL = "faw.json"

# Datos locales que no se publican. Mismo archivo que lee la compuerta de superficie.
ARCHIVO_LOCAL = "config.json"

# Gestores de tickets reconocidos. `interno` es el registro propio de FAW, que no
# depende de ningun servicio; `ninguno` lo desactiva y deja solo el identificador
# que las rutas de recibos necesitan.
SISTEMAS_TICKET = ("ado", "jira", "github", "interno", "ninguno")

# Servidor MCP que sabe operar cada gestor. Si esta disponible en la sesion, el
# agente crea y actualiza tickets ahi en vez de pedirselo al usuario. Si no lo
# esta, el gestor sigue siendo el declarado y el agente trabaja contra el a mano.
MCP_POR_SISTEMA = {
    "ado": "mcp__ado__*",
    "github": "mcp__github__*",
}

PROMOCIONES = ("deployment-pipeline", "git", "manual", "ninguna")

DEFECTOS = {
    "tickets": {"sistema": "interno", "proyecto": None, "organizacion": None},
    "ambientes": {"dev": False, "prd": True, "promocion": "manual"},
    "canal": {"livy": False, "tabla_control": None, "skills_microsoft": None,
              "servidores_mcp": None},
}


def _leer(archivo: Path, etiqueta: str) -> dict:
    """Lee un JSON de configuracion. Un archivo ilegible avisa, no se ignora.

    Degradarse en silencio ante un JSON mal formado es el modo de fallo que el
    principio 4 prohibe: el metodo seguiria corriendo con la mitad de sus reglas
    y todo se veria normal. Se devuelve vacio para no frenar el trabajo, pero el
    aviso sale por stderr para que el error sea visible en el momento.
    """
    if not archivo.exists():
        return {}
    try:
        crudo = json.loads(archivo.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[faw] {etiqueta} existe pero no se pudo leer ({e}). "
              f"Se sigue con los valores por defecto, que son los mas estrictos. "
              f"Corregir el archivo: mientras tanto sus reglas no se estan aplicando.",
              file=sys.stderr)
        return {}
    if not isinstance(crudo, dict):
        print(f"[faw] {etiqueta} no contiene un objeto JSON. Se ignora.", file=sys.stderr)
        return {}
    return crudo


def _fusionar(declarado: dict, defecto: dict) -> dict:
    """Completa las claves ausentes sin pisar lo declarado.

    Clave por clave y no seccion por seccion: declarar `ambientes.dev` no debe
    borrar `ambientes.promocion`. Un perfil parcial es el caso normal.
    """
    salida = dict(defecto)
    if isinstance(declarado, dict):
        for k, v in declarado.items():
            if v is not None:
                salida[k] = v
    return salida


def _avisar_claves_desconocidas(crudo: dict) -> None:
    """Una clave que FAW no entiende se avisa en vez de ignorarse.

    Un `ambeintes` mal tipeado no debe pasar por perfil valido: la regla que el
    usuario creyo declarar no se estaria aplicando, y nada se lo diria.
    """
    for seccion in crudo:
        if seccion in DEFECTOS:
            desconocidas = set(crudo[seccion] or {}) - set(DEFECTOS[seccion])
            if desconocidas:
                print(f"[faw] {ARCHIVO_PERFIL}: claves no reconocidas en '{seccion}': "
                      f"{', '.join(sorted(desconocidas))}. No se aplican.", file=sys.stderr)
        else:
            print(f"[faw] {ARCHIVO_PERFIL}: seccion no reconocida '{seccion}'. No se aplica.",
                  file=sys.stderr)


def perfil(repo: Path) -> dict:
    """Perfil normalizado del proyecto, con los defectos estrictos aplicados."""
    crudo = _leer(repo / ARCHIVO_PERFIL, ARCHIVO_PERFIL)
    _avisar_claves_desconocidas(crudo)

    p = {seccion: _fusionar(crudo.get(seccion) or {}, DEFECTOS[seccion])
         for seccion in DEFECTOS}

    sistema = str(p["tickets"].get("sistema") or "").strip().lower()
    p["tickets"]["sistema"] = sistema if sistema in SISTEMAS_TICKET else "interno"

    promocion = str(p["ambientes"].get("promocion") or "").strip().lower()
    p["ambientes"]["promocion"] = promocion if promocion in PROMOCIONES else "manual"

    p["ambientes"]["dev"] = bool(p["ambientes"].get("dev"))
    p["ambientes"]["prd"] = bool(p["ambientes"].get("prd", True))
    p["canal"]["livy"] = bool(p["canal"].get("livy"))

    p["declarado"] = bool(crudo)
    return p


def local(repo: Path) -> dict:
    """Datos locales sin versionar: nombres, literales, rutas de esta maquina."""
    return _leer(repo / ".faw" / ARCHIVO_LOCAL, ".faw/" + ARCHIVO_LOCAL)


def ambiente_unico(p: dict) -> bool:
    """Verdadero cuando no hay ambiente de desarrollo separado del productivo."""
    return not p["ambientes"]["dev"]


def exige_autorizacion_escrita(p: dict) -> bool:
    """Si cada escritura al tenant debe dejar el motivo por escrito antes de correr.

    Es la consecuencia mecanica de `ambientes.dev`. Con un ambiente de pruebas,
    equivocarse es barato y alcanza con la autorizacion conversada del turno. Sin
    el, toda escritura cae sobre datos que alguien esta usando, y la autorizacion
    pasa de ser una declaracion del agente a un archivo que el hook comprueba.
    """
    return ambiente_unico(p)


def regla_de_escritura(p: dict) -> str:
    """La regla de autorizacion que rige en este proyecto, en una linea."""
    if ambiente_unico(p):
        return ("Ambiente unico, tratado como productivo: toda escritura al tenant necesita "
                "autorizacion por escrito en .faw/autorizacion-tenant.txt antes de ejecutarse.")
    return ("Escrituras en desarrollo: autorizacion explicita del usuario en el turno. "
            "Cambios en produccion: autorizacion explicita, siempre.")


def registro_de_corrida(p: dict) -> str:
    """Donde queda constancia de una ejecucion que escribio en el tenant."""
    tabla = p["canal"].get("tabla_control")
    if tabla:
        return f"Registrar la corrida en {tabla} y en el recibo del ticket."
    return "Registrar la corrida en el recibo del ticket."


def mcp_de_tickets(p: dict) -> str | None:
    """Servidor MCP que opera el gestor declarado, si existe uno conocido."""
    return MCP_POR_SISTEMA.get(p["tickets"]["sistema"])


def linea_de_contexto(p: dict) -> str:
    """Una linea con lo que cambia decisiones en este proyecto, para inyectar por turno.

    Una sola linea, y solo lo que altera lo que el agente puede hacer sin
    preguntar. El hook que la usa declara su presupuesto: lo que narra en cada
    turno entrena a dejar de leerlo.
    """
    partes = [regla_de_escritura(p)]
    sistema = p["tickets"]["sistema"]
    if sistema == "interno":
        partes.append("Tickets: registro interno de FAW (docs/faw/tickets/).")
    elif sistema != "ninguno":
        mcp = mcp_de_tickets(p)
        partes.append(f"Tickets: {sistema}" + (f" (via {mcp} si esta disponible)." if mcp else "."))
    return " ".join(partes)
