#!/usr/bin/env python3
"""
Piezas compartidas por los hooks: leer la entrada, leer el estado, denegar.

Cada hook recibe el mismo JSON por stdin y responde con el mismo formato. Tener
esa mecanica en un solo lugar evita que una correccion se aplique en un hook y
no en los otros, que es como una compuerta queda silenciosamente distinta de las
demas.

El detalle de encoding no es cosmetico: en Windows stdout usa cp1252 por
defecto, y un caracter fuera de ese conjunto hace crashear el proceso. Un hook
que crashea sale con codigo distinto de cero, y Claude Code trata eso como *no
bloqueante*: el hook roto se ve igual que el hook que aprueba. Por eso stdin se
lee como bytes y se decodifica explicito, y stdout se reconfigura a UTF-8.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def preparar_salida() -> None:
    """Fuerza UTF-8 en stdout. Silencioso si el runtime no lo permite."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def entrada() -> dict | None:
    """El JSON que manda Claude Code, o None si no se puede parsear.

    Devolver None significa fallar abierto. Es deliberado: un error de parseo en
    el hook no debe frenar todo el trabajo del usuario. La compuerta existe para
    atajar un error concreto, no para volverse ella misma el punto de falla.
    """
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def activo(repo: Path) -> bool:
    """FAW gobierna este repo solo si existe el directorio `.faw/`.

    Es el opt-in del metodo: instalar el plugin no impone el proceso a proyectos
    que no lo pidieron.
    """
    return (repo / ".faw").is_dir()


def leer_estado(repo: Path) -> dict | None:
    """Ultima entrada de `.faw/estado.jsonl`, o None si no hay trabajo abierto.

    El archivo es un log de eventos, no un documento: el estado vigente es la
    ultima linea valida. Las lineas ilegibles se saltean en vez de abortar,
    para que un archivo parcialmente escrito no deje al metodo sin estado.
    """
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


def fase_de(estado: dict | None) -> str | None:
    """Nombre de la fase vigente, tolerando la clave en espanol o en ingles."""
    if not estado:
        return None
    return estado.get("fase") or estado.get("phase")


def denegar(motivo: str) -> int:
    """Deniega la llamada explicando por que, en el formato que espera el hook.

    Se usa la forma JSON en vez de exit 2 porque el motivo llega a Claude como
    dato estructurado y no como texto de error, lo que hace la diferencia entre
    un agente que corrige el rumbo y uno que reintenta lo mismo.
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }, ensure_ascii=False))
    return 0


def consumir_override(repo: Path, nombre: str) -> str | None:
    """Lee y borra un archivo de autorizacion de un solo uso.

    El archivo se borra al leerse para que una excepcion puntual no quede como
    un permiso permanente que nadie recuerda haber dado. Devuelve el motivo
    declarado, o None si no existe o esta vacio.
    """
    f = repo / ".faw" / nombre
    if not f.exists():
        return None
    try:
        motivo = f.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    if not motivo:
        return None
    f.unlink()
    return motivo
