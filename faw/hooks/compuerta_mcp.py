#!/usr/bin/env python3
"""
Hook PreToolUse sobre herramientas MCP — extiende las fases a las escrituras
que no pasan por Write/Edit.

## El hueco que cierra

Las compuertas de fase se aplicaban solo a las herramientas de edicion de
archivos. Una escritura contra el tenant hecha por un servidor MCP —crear un
item, subir un archivo a OneLake, modificar un modelo semantico— no tocaba
ningun archivo del repo y por lo tanto no pasaba por ninguna compuerta. El
efecto practico era que las fases gobernaban el codigo y no el dato: se podia
estar en PERFILADO, que es de solo lectura por definicion, y escribir en el
tenant igual.

Las herramientas de un servidor MCP se presentan a los hooks como cualquier otra
herramienta, con el nombre `mcp__<servidor>__<herramienta>`, asi que un matcher
las alcanza. Eso es lo que hace posible esta compuerta.

## Por que hace falta y no alcanza con confiar en el servidor

La documentacion de Microsoft sobre sus servidores MCP para Fabric advierte que
un cliente autonomo o mal configurado puede ejecutar operaciones destructivas, y
que los mecanismos para impedirlo no estan estandarizados en la especificacion
MCP ni implementados por todos los clientes. La consecuencia de diseno es que la
salvaguarda tiene que vivir en el orquestador. Este hook es esa salvaguarda.

## Lectura y escritura no se tratan igual

Bloquear toda herramienta MCP romperia el metodo en vez de reforzarlo: PERFILADO
existe para medir el origen, y medirlo requiere leerlo. La compuerta distingue
por nombre de herramienta y, ante la duda, clasifica como escritura. El error de
clasificar de mas una lectura cuesta una autorizacion innecesaria; el de
clasificar de menos una escritura la deja pasar sin control.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import comun  # noqa: E402
import perfil as perfil_mod  # noqa: E402

# Verbos de solo lectura. Se comparan contra el nombre de la herramienta, ya sin
# el prefijo del servidor. La lista es conservadora a proposito: agregar un verbo
# de lectura que faltaba cuesta una linea; sacar uno que en realidad escribia
# cuesta un dato mal escrito que nadie vio.
VERBOS_LECTURA = (
    "list", "get", "read", "search", "describe", "show", "query", "fetch",
    "find", "docs", "inspect", "preview", "count", "check", "validate",
    "download",
)

# Herramientas de solo lectura por diseno del servidor, mas alla de su nombre.
# `execute_query` del endpoint SQL de Fabric consulta un endpoint que no admite
# INSERT, UPDATE ni DELETE: el nombre parece de escritura y la operacion no lo es.
LECTURA_EXPLICITA = {
    "execute_query",
    "execute_dax_query",
}

# Nombres que ejecutan codigo o definicion arbitraria. Aunque su verbo parezca
# inocuo, lo que corre adentro puede escribir.
ESCRITURA_EXPLICITA = {
    "run_statement",
    "livy_run_statement",
    "execute_sql",
    "apply_migration",
}

# La compuerta se limita a los servidores que operan la plataforma de datos. Un
# proyecto puede tener conectado un servidor de calendario o de correo, y frenar
# esas llamadas por la fase de un trabajo de datos seria ruido sin ningun fallo
# detras. Se compara como subcadena del nombre del servidor.
SERVIDORES_DE_DATOS = ("fabric", "powerbi", "power-bi", "onelake", "synapse",
                       "databricks", "sqlendpoint", "sql-endpoint")


def _partes(tool: str) -> tuple[str, str] | None:
    """Servidor y herramienta a partir de `mcp__<servidor>__<herramienta>`."""
    if not tool.startswith("mcp__"):
        return None
    resto = tool[len("mcp__"):]
    if "__" not in resto:
        return None
    servidor, herramienta = resto.split("__", 1)
    return servidor, herramienta


def es_lectura(herramienta: str) -> bool:
    """Clasifica una herramienta MCP. Ante la duda, no es lectura."""
    h = herramienta.lower()
    if h in ESCRITURA_EXPLICITA:
        return False
    if h in LECTURA_EXPLICITA:
        return True
    primer_verbo = h.split("_", 1)[0]
    return primer_verbo in VERBOS_LECTURA


def main() -> int:
    comun.preparar_salida()

    entrada = comun.entrada()
    if entrada is None:
        return 0

    repo = Path(entrada.get("cwd") or ".")
    if not comun.activo(repo):
        return 0

    tool = entrada.get("tool_name") or ""
    partes = _partes(tool)
    if partes is None:
        return 0
    servidor, herramienta = partes

    p = perfil_mod.perfil(repo)
    conocidos = tuple(p["canal"].get("servidores_mcp") or ()) + SERVIDORES_DE_DATOS
    if not any(c.lower() in servidor.lower() for c in conocidos):
        return 0

    if es_lectura(herramienta):
        return 0

    estado = comun.leer_estado(repo)
    fase = comun.fase_de(estado)

    if not estado or fase in (None, "IDLE"):
        return comun.denegar(
            f"FAW: escritura al tenant denegada. `{tool}` modifica el ambiente y no hay "
            "trabajo clasificado.\n"
            "Una escritura sin ticket abierto no queda registrada en ningun lado: no hay "
            "recibo al que atarla ni fase que la justifique.\n"
            "Clasificar primero (tier y alcance, con el OK del usuario) y despues registrar "
            "el trabajo con estado.py.\n"
            "Si solo hace falta leer, usar una herramienta de consulta: la lectura no "
            "requiere clasificacion."
        )

    if fase == "CLASIFICACION":
        return comun.denegar(
            f"FAW: escritura al tenant denegada. La fase es CLASIFICACION, que se cierra "
            f"acordando alcance con el usuario, no tocando el ambiente.\n"
            f"`{tool}` escribe. Mover de fase primero, con el OK del usuario registrado "
            "como compuerta."
        )

    if fase == "PERFILADO":
        return comun.denegar(
            f"FAW: escritura al tenant denegada. La fase es PERFILADO, que es de solo "
            f"lectura por definicion: se mide el origen tal como esta, sin alterarlo.\n"
            f"`{tool}` escribe. Si de verdad hace falta escribir para poder perfilar "
            "(una tabla temporal, por ejemplo), eso es una decision del usuario: "
            "planteala y avanza de fase con su autorizacion."
        )

    if perfil_mod.exige_autorizacion_escrita(p):
        motivo = comun.consumir_override(repo, "autorizacion-tenant.txt")
        if not motivo:
            return comun.denegar(
                f"FAW: escritura al tenant denegada. `{tool}` escribe en {servidor}, y este "
                "proyecto no declara un ambiente de desarrollo separado: lo que se escriba "
                "cae sobre datos que alguien esta usando.\n"
                f"{perfil_mod.regla_de_escritura(p)}\n"
                "Escribir el motivo y la operacion en .faw/autorizacion-tenant.txt y "
                "reintentar. El archivo se consume al usarse, para que una autorizacion "
                "puntual no quede como permiso permanente.\n"
                "El hook corre ANTES del comando: escribir el archivo y ejecutar en la "
                "misma llamada no funciona, porque en ese momento todavia no existe."
            )
        print(f"[faw] escritura al tenant autorizada por escrito: {motivo}", file=sys.stderr)
        return 0

    # Hay ambiente de desarrollo: la autorizacion del turno sigue siendo una
    # declaracion del agente, no algo que este hook pueda comprobar. Se recuerda
    # la regla del proyecto en vez de simular una verificacion que no existe.
    print(
        f"[faw] `{tool}` escribe en {servidor}. {perfil_mod.regla_de_escritura(p)} "
        f"{perfil_mod.registro_de_corrida(p)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
