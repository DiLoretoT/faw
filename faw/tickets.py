#!/usr/bin/env python3
"""
Registro de tickets interno: el gestor que existe cuando no hay ninguno.

## Por que hace falta

El metodo necesita un identificador de trabajo para nombrar sus recibos y para
que la pregunta "en que quedamos" tenga una respuesta que sobreviva cerrar la
sesion. Ese identificador suele venir de un gestor externo, pero exigir uno
convierte una herramienta de gestion en requisito de instalacion: quien no usa
ninguno terminaria inventando identificadores para satisfacer al metodo, y un
identificador inventado no remite a nada.

Este modulo resuelve el caso sin depender de ningun servicio. El ticket es un
archivo markdown en el repo de trabajo, y el historial lo aporta git: quien
quiera saber como cambio el alcance de un trabajo lee el log del archivo. Eso es
lo que un gestor externo ofrece y un archivo suelto no: rastro de las
modificaciones.

## Que gana un proyecto que si tiene gestor

Nada de esto lo reemplaza. Si el perfil declara `ado`, `jira` o `github`, el
identificador sale de ahi y este registro no se usa. La diferencia esta en si
existe un servidor MCP para ese gestor: con MCP, el agente consulta y actualiza
el ticket directamente; sin MCP, el gestor sigue siendo la fuente del
identificador y el usuario opera la herramienta. En los dos casos el metodo
funciona igual, porque lo unico que necesita de un ticket es su identificador.

## Por que los tickets se versionan y pasan por la compuerta de superficie

Un ticket contiene, por naturaleza, preguntas abiertas y tareas para personas
del negocio. Es exactamente el contenido que no debe llegar a un repo que lee un
tercero. Por eso el registro vive bajo `docs/faw/tickets/`, que la compuerta de
superficie revisa, a diferencia del resto de `docs/faw/`. Si el destinatario del
repo no debe leer los tickets, el proyecto declara otra raiz de artefactos.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

DIR_TICKETS = Path("docs") / "faw" / "tickets"

ESTADOS = ("abierto", "en-curso", "pausado", "cerrado", "abandonado")

# Un identificador termina siendo un nombre de directorio (`docs/faw/<id>/`). Los
# caracteres que Windows prohibe en una ruta romperian la escritura del recibo
# recien al final del trabajo, cuando ya no hay nada que hacer al respecto.
RE_ID_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def sanitizar(identificador: str) -> str | None:
    """Devuelve el identificador si sirve como nombre de ruta, o None."""
    ident = (identificador or "").strip()
    return ident if RE_ID_VALIDO.match(ident) else None


def _proximo_numero(repo: Path) -> int:
    """Siguiente numero libre del registro interno.

    Se calcula leyendo los archivos existentes y no guardando un contador: un
    contador en un archivo aparte se desincroniza en cuanto dos personas crean un
    ticket en ramas distintas, y el conflicto aparece en un lugar que no explica
    nada.
    """
    d = repo / DIR_TICKETS
    if not d.is_dir():
        return 1
    usados = []
    for f in d.glob("T-*.md"):
        m = re.match(r"^T-(\d+)$", f.stem)
        if m:
            usados.append(int(m.group(1)))
    return max(usados, default=0) + 1


def nuevo_identificador(repo: Path) -> str:
    """Identificador correlativo del registro interno, con el formato `T-007`.

    Correlativo y no derivado del titulo: un identificador derivado de texto
    obliga a sanitizar, puede colisionar y cambia si el titulo se corrige. El
    numero no tiene ninguno de esos problemas y ordena por antiguedad.
    """
    return f"T-{_proximo_numero(repo):03d}"


def ruta(repo: Path, identificador: str) -> Path:
    return repo / DIR_TICKETS / f"{identificador}.md"


def crear(repo: Path, identificador: str, titulo: str, tier: str,
          alcance: str = "", fuera_de_alcance: str = "") -> Path:
    """Escribe el ticket con lo acordado en CLASIFICACION.

    Las secciones no son decorativas: son las cuatro preguntas que la fase tiene
    que responder. Un ticket sin "que NO entra" documenta una intencion, no un
    alcance, y es el hueco por el que un trabajo crece sin que nadie lo decida.
    """
    f = ruta(repo, identificador)
    f.parent.mkdir(parents=True, exist_ok=True)
    hoy = date.today().isoformat()
    f.write_text(
        f"# {identificador} — {titulo}\n\n"
        f"| | |\n|---|---|\n"
        f"| Estado | abierto |\n"
        f"| Tier | {tier} |\n"
        f"| Creado | {hoy} |\n\n"
        f"## Qué se pide\n\n{alcance or '<una frase, reformulando el pedido>'}\n\n"
        f"## Qué NO entra\n\n{fuera_de_alcance or '<lo que queda explícitamente afuera>'}\n\n"
        f"## Registro\n\n- {hoy} — abierto\n",
        encoding="utf-8",
    )
    return f


def registrar(repo: Path, identificador: str, evento: str) -> bool:
    """Agrega una linea al registro del ticket. Falso si el ticket no existe."""
    f = ruta(repo, identificador)
    if not f.exists():
        return False
    contenido = f.read_text(encoding="utf-8-sig").rstrip("\n")
    contenido += f"\n- {date.today().isoformat()} — {evento}\n"
    f.write_text(contenido, encoding="utf-8")
    return True


def actualizar_estado(repo: Path, identificador: str, estado: str) -> bool:
    """Cambia el estado declarado en la tabla de cabecera."""
    if estado not in ESTADOS:
        return False
    f = ruta(repo, identificador)
    if not f.exists():
        return False
    contenido = f.read_text(encoding="utf-8-sig")
    nuevo = re.sub(r"^\| Estado \| .* \|$", f"| Estado | {estado} |",
                   contenido, count=1, flags=re.MULTILINE)
    f.write_text(nuevo, encoding="utf-8")
    return True


def listar(repo: Path) -> list[tuple[str, str, str]]:
    """Tickets del registro interno como (identificador, estado, titulo)."""
    d = repo / DIR_TICKETS
    if not d.is_dir():
        return []
    salida = []
    for f in sorted(d.glob("*.md")):
        texto = f.read_text(encoding="utf-8-sig", errors="replace")
        m_estado = re.search(r"^\| Estado \| (.+?) \|$", texto, re.MULTILINE)
        m_titulo = re.search(r"^# \S+ — (.+)$", texto, re.MULTILINE)
        salida.append((f.stem,
                       m_estado.group(1).strip() if m_estado else "?",
                       m_titulo.group(1).strip() if m_titulo else ""))
    return salida
