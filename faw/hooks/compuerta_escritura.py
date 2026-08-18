#!/usr/bin/env python3
"""
Hook PreToolUse (Write|Edit|NotebookEdit) — convierte las fases en obligatorias
en vez de opcionales.

Dos cosas hace, y las dos salen de fallos reales:

1. **Deniega la primera escritura si no hay CLASIFICACION registrado.** Antes,
   `estado.py` solo mordia si el agente elegia invocarlo: se podia construir un
   artefacto entero sin tocar la maquina de estados. Ahora saltear la clasificación
   deja de ser un olvido silencioso.

2. **Deniega escrituras cuando la fase es PERFILADO.** Perfilar es solo lectura
   por definicion (principio 3 y fases.md §2). No se puede lograr con
   `disallowed-tools` de una skill: la doc oficial dice que esa restriccion "se
   limpia cuando mandas el siguiente mensaje", asi que no sostiene una fase.
   Un hook si.

Formato verificado contra la doc oficial de Claude Code
(code.claude.com/docs/en/hooks, leida el 2026-08-04):
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "..."}}
`permissionDecision` acepta allow / deny / ask / defer. Se usa la forma JSON en
vez de exit 2 porque el motivo llega estructurado y no como texto de error.

LO QUE ESTE HOOK NO CUBRE, dicho explicito: escribir un archivo desde `Bash`
(heredoc, `>`, `tee`) no pasa por PreToolUse de Write/Edit. Igual que con Livy,
aca el metodo detecta pero no previene. Prometer lo contrario seria mentir sobre
una compuerta.

Opt-in: no hace nada salvo que el proyecto tenga un directorio `.faw/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ruta real de ESTA instalacion, para que el mensaje del hook de el comando
# exacto sin asumir donde esta clonado o cacheado el plugin.
ESTADO_PY = Path(__file__).resolve().parent.parent.parent / "scripts" / "estado.py"

# Rutas que se pueden escribir SIEMPRE: son los recibos y el estado del propio
# metodo. Sin esta excepcion, PERFILADO no podria producir su recibo y el
# clasificación no podria registrarse — la compuerta se bloquearia a si misma.
PREFIJOS_LIBRES = (".faw", "docs/faw")


def _estado(repo: Path) -> dict | None:
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


def _denegar(motivo: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }, ensure_ascii=False))
    return 0


def _destino(entrada: dict) -> str:
    ti = entrada.get("tool_input") or {}
    return ti.get("file_path") or ti.get("notebook_path") or ""


def _fuera_del_repo(repo: Path, destino: str) -> bool:
    """
    FAW gobierna el repo, no el disco.

    Un archivo cuyo destino cae afuera de la raiz del repo no es un artefacto del
    proyecto, asi que la compuerta no le aplica. Sin esta comprobacion cualquier
    escritura a una ruta externa queda bloqueada solo porque el proceso tiene su
    cwd en un repo gobernado — bloquear una nota personal o un script temporal no
    protege nada y hace que la compuerta parezca arbitraria.

    Si no hay destino legible se devuelve False: no se puede decidir a favor, y
    ante la duda se sigue evaluando.
    """
    if not destino:
        return False
    try:
        Path(destino).resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        return True
    return False


def _es_libre(repo: Path, destino: str) -> bool:
    """Rutas del propio metodo (recibos, estado): se pueden escribir siempre."""
    if not destino:
        return False
    try:
        rel = Path(destino).resolve().relative_to(repo.resolve()).as_posix()
    except (ValueError, OSError):
        return False  # lo de afuera del repo lo resuelve _fuera_del_repo
    return any(rel == p or rel.startswith(p + "/") for p in PREFIJOS_LIBRES)


def main() -> int:
    # Ver la nota de encoding en inyectar_contexto.py: en Windows stdout es cp1252
    # y un caracter fuera de ese set hace crashear el hook, que entonces no bloquea.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        crudo = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        entrada = json.loads(crudo)
    except json.JSONDecodeError:
        return 0  # fallar abierto: un error de parseo del hook no debe frenar todo

    repo = Path(entrada.get("cwd") or ".")

    # --- Opt-in ---------------------------------------------------------------
    if not (repo / ".faw").is_dir():
        return 0

    destino = _destino(entrada)
    if _fuera_del_repo(repo, destino):
        return 0
    if _es_libre(repo, destino):
        return 0

    st = _estado(repo)
    fase = (st or {}).get("fase") or (st or {}).get("phase")

    if not st or fase in (None, "IDLE"):
        return _denegar(
            "FAW: escritura denegada porque no hay trabajo clasificado.\n"
            "Antes de escribir hay que cerrar CLASIFICACION: reformular el pedido en una frase, "
            "asignar tier, definir que entra y que NO, y esperar el OK del usuario.\n"
            "Despues registrarlo:\n"
            f"  python {ESTADO_PY} iniciar --ticket <T> --tier <TIER> --titulo \"<t>\"\n"
            "Si es una CONSULTA (no toca nada), no hace falta clasificar: responder sin escribir."
        )

    if fase == "CLASIFICACION":
        # Hueco encontrado probando (no leyendo): la primera version solo denegaba
        # en IDLE y PERFILADO, asi que bastaba `iniciar` para escribir lo que sea —
        # o sea, saltarse el punto de control 1 con un comando. CLASIFICACION
        # produce "la clasificacion, en el chat, sin documento": aca no se construye.
        # El brief SI se escribe aca, y pasa por la excepcion de docs/faw/.
        return _denegar(
            "FAW: escritura denegada porque la fase es CLASIFICACION, que se cierra "
            "conversando, no construyendo (fases.md §1).\n"
            "Falta: acordar tier y alcance con el usuario, esperar su OK, y recien "
            "despues mover de fase:\n"
            f"  python {ESTADO_PY} mover --a <FASE> --compuerta confirmacion_usuario=\"...\"\n"
            "Excepcion que si se puede escribir aca: docs/faw/<ticket>/brief.md (tier REPORTE)."
        )

    if fase == "PERFILADO":
        return _denegar(
            "FAW: escritura denegada porque la fase es PERFILADO, que es solo lectura "
            "(fases.md §2 y principio 3).\n"
            "El recibo del perfilado si se puede escribir: va en docs/faw/<ticket>/perfilado.md, "
            "con cada numero acompanado de la consulta que lo produjo.\n"
            "Si de verdad hace falta escribir en el tenant para perfilar, eso necesita "
            "autorizacion explicita del usuario en este turno, y despues avanzar de fase."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
