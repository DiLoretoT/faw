#!/usr/bin/env python3
"""
Maquina de estados de FAW.

Registra y valida transiciones entre fases. El historial vive en .faw/estado.jsonl,
solo-append: no para auditoria formal, sino para que cuando alguien retome dentro
de dos semanas la respuesta a "en que quedamos" no dependa de la memoria de nadie.

Uso
---
  python estado.py iniciar --ticket T-12 --tier ARTEFACTO --titulo "dim_proveedor"
  python estado.py estado
  python estado.py mover --a PERFILADO
  python estado.py mover --a DISENO --compuerta perfil=docs/faw/T-12/perfilado.md
  python estado.py pausar --motivo "esperando confirmacion de Contabilidad"
  python estado.py abandonar --motivo "el requerimiento cambio"

Las compuertas de fuerza 'maquina' NO se satisfacen con --compuerta: hay que
correr su script y este las verifica sola. Las de 'recibo' exigen que el archivo
exista. Las de 'declaracion' se registran con --compuerta clave="texto".

Las compuertas por-tabla (`contrato`, `esquema`) emiten un recibo POR TABLA.
Si el ticket toca mas de una, declarar el alcance en el mover:

  python estado.py mover --a CONSTRUCCION --compuerta tablas=gold.dim_a,gold.fact_b

y la compuerta exige el recibo valido de CADA tabla declarada. Con una sola
tabla no hace falta declarar nada.

Salida: 0 si la transicion es valida y quedo registrada, 1 si se rechaza.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path.cwd()
DIR_ESTADO = RAIZ / ".faw"
LOG = DIR_ESTADO / "estado.jsonl"
FAW = Path(__file__).resolve().parent.parent
TRANSICIONES = FAW / "faw" / "transiciones.json"

sys.path.insert(0, str(FAW))
from faw import perfil as perfil_mod  # noqa: E402
from faw import recibos  # noqa: E402
from faw import tickets as tickets_mod  # noqa: E402


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except FileNotFoundError:
        return None


def _git_limpio() -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain"],
                             capture_output=True, text=True)
        return out.returncode == 0 and not out.stdout.strip()
    except FileNotFoundError:
        return False


def cargar_reglas() -> dict:
    if not TRANSICIONES.exists():
        print(f"ERROR: no existe {TRANSICIONES}", file=sys.stderr)
        sys.exit(2)
    return json.loads(TRANSICIONES.read_text(encoding="utf-8"))


def leer_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def escribir(entrada: dict) -> None:
    DIR_ESTADO.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def actual() -> dict | None:
    log = leer_log()
    return log[-1] if log else None


# Compuertas cuyo verificador trabaja de a una tabla. El recibo se emite por
# tabla y la compuerta tiene que exigir el de CADA tabla del ticket: con el
# recibo unico, un ticket de 9 tablas cerraba la fase probando solo la ultima.
COMPUERTAS_POR_TABLA = {"contrato", "esquema"}


def _verificar_por_tabla(n: str, d: dict, declaradas: dict[str, str],
                         fallos: list[str]) -> None:
    """
    Verifica una compuerta por-tabla.

    El conjunto esperado lo declara el agente en el mover:
    `--compuerta tablas=gold.dim_a,gold.fact_b`. La declaracion fija el alcance
    (es una declaracion: la maquina no puede saber cuantas tablas toca el
    ticket); la verificacion de cada recibo sigue siendo de maquina.

    Sin declaracion: con un solo recibo emitido se verifica ese (el caso
    mono-tabla, la mayoria); con mas de uno se rechaza pidiendo la declaracion —
    adivinar el conjunto seria repetir el gap con otra cara.
    """
    sufijo = f"  [correr: {d.get('verifica')}]"
    crudo = (declaradas.get("tablas") or "").strip()

    if crudo:
        tablas = [t.strip() for t in crudo.split(",") if t.strip()]
        if not tablas:
            fallos.append(f"{n}: la declaracion 'tablas' esta vacia")
            return
        for t in tablas:
            ok, motivo = recibos.verificar(n, ambito=t)
            if not ok:
                fallos.append(f"{n} [{t}]: {motivo}{sufijo}")
        return

    emitidos = recibos.listar(n)
    ambitos = sorted(a for a in emitidos if a is not None)

    if len(ambitos) > 1:
        fallos.append(
            f"{n}: hay recibos de {len(ambitos)} tablas ({', '.join(ambitos)}) y el "
            f"ticket no declaro cuales toca. Declara el alcance con "
            f"--compuerta tablas=<t1,t2,...> para que la compuerta exija el recibo "
            f"de CADA una, no solo del ultimo verificado")
        return

    if len(ambitos) == 1:
        ok, motivo = recibos.verificar(n, ambito=ambitos[0])
        if not ok:
            fallos.append(f"{n} [{ambitos[0]}]: {motivo}{sufijo}")
        return

    # Legado: recibo unico sin ambito (emitido por una version anterior).
    ok, motivo = recibos.verificar(n)
    if not ok:
        fallos.append(f"{n}: {motivo}{sufijo}")


def _pertenece_al_ticket(absoluta: Path, declarada: str, ticket: str) -> bool:
    """Si un documento puede afirmarse como recibo del ticket en curso.

    Vale que el ticket aparezca en la ruta, que es la convencion habitual, o en
    el texto del documento, que cubre los proyectos que guardan sus artefactos
    fuera del repo con otra estructura de carpetas.
    """
    if ticket in str(declarada):
        return True
    try:
        return ticket in absoluta.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False


def verificar_compuertas(nombres: list[str], reglas: dict,
                         declaradas: dict[str, str],
                         ticket: str | None = None) -> tuple[bool, list[str]]:
    defs = reglas.get("compuertas", {})
    fallos: list[str] = []

    for n in nombres:
        d = defs.get(n, {})
        fuerza = d.get("fuerza", "declaracion")

        if fuerza == "maquina":
            if n == "git-limpio":
                if not _git_limpio():
                    fallos.append("git-limpio: hay cambios sin comitear")
                continue
            if n in COMPUERTAS_POR_TABLA:
                _verificar_por_tabla(n, d, declaradas, fallos)
                continue
            # Las demas exigen el recibo que emitio su verificador. Ya NO se
            # satisfacen con un string: `estado.py` recomputa el hash de los
            # insumos y rechaza el recibo si alguno cambio.
            ok, motivo = recibos.verificar(n, exigir_commit_actual=(n == "metadata"))
            if not ok:
                fallos.append(f"{n}: {motivo}  [correr: {d.get('verifica')}]")
            continue

        if fuerza == "recibo":
            # `contrato` lo emite el propio verificador; el resto son documentos
            # cuya ruta declara el agente.
            if n in COMPUERTAS_POR_TABLA:
                _verificar_por_tabla(n, d, declaradas, fallos)
                continue
            ruta = declaradas.get(n)
            if not ruta:
                fallos.append(f"{n}: falta la ruta del recibo")
            elif not (RAIZ / ruta).exists():
                fallos.append(f"{n}: el recibo '{ruta}' no existe")
            elif (RAIZ / ruta).stat().st_size < 200:
                fallos.append(f"{n}: '{ruta}' tiene menos de 200 bytes — "
                              f"un recibo de perfilado sin consultas no es un recibo")
            elif ticket and not _pertenece_al_ticket(RAIZ / ruta, ruta, ticket):
                # Sin esta atadura, cualquier archivo de mas de 200 bytes cierra la
                # compuerta: que el recibo fuera el del trabajo en curso lo sostenia
                # una convencion de nombres, no el codigo. Se acepta que el ticket
                # aparezca en la ruta o adentro del documento, porque un proyecto
                # puede guardar sus artefactos fuera del repo con otra estructura.
                fallos.append(f"{n}: '{ruta}' no menciona al ticket {ticket} ni en su ruta "
                              f"ni en su contenido, asi que no se puede afirmar que sea el "
                              f"recibo de este trabajo.")
            continue

        if n not in declaradas or not declaradas[n].strip():
            fallos.append(f"{n}: falta la declaracion")

    return (not fallos), fallos


def cmd_iniciar(a) -> int:
    reglas = cargar_reglas()
    tiers = list(reglas.get("tiers", {}))
    if a.tier not in tiers:
        print(f"Tier desconocido: '{a.tier}'.\nTiers validos: {', '.join(tiers)}",
              file=sys.stderr)
        return 1
    act = actual()
    if act and act.get("fase") != "IDLE":
        print(f"Ya hay trabajo abierto: {act['ticket']} en {act['fase']}.\n"
              f"Cerralo, pausalo o abandonalo antes de empezar otro.", file=sys.stderr)
        return 1
    p = perfil_mod.perfil(RAIZ)
    sistema = p["tickets"]["sistema"]

    ticket = a.ticket
    if ticket:
        limpio = tickets_mod.sanitizar(ticket)
        if not limpio:
            print(f"Identificador invalido: '{ticket}'.\n"
                  f"Se usa como nombre de directorio (docs/faw/<ticket>/), asi que solo "
                  f"admite letras, numeros, punto, guion y guion bajo.", file=sys.stderr)
            return 1
        ticket = limpio
    elif sistema == "interno":
        ticket = tickets_mod.nuevo_identificador(RAIZ)
    else:
        print(f"Falta --ticket. Este proyecto declara '{sistema}' como gestor de tickets "
              f"en {perfil_mod.ARCHIVO_PERFIL}, asi que el identificador sale de ahi.\n"
              f"Si el trabajo no tiene ticket en {sistema}, crearlo primero: un trabajo "
              f"sin registro externo queda invisible para el resto del equipo.",
              file=sys.stderr)
        return 1

    if sistema == "interno" and not tickets_mod.ruta(RAIZ, ticket).exists():
        tickets_mod.crear(RAIZ, ticket, a.titulo, a.tier)

    escribir({"ts": _ahora(), "evento": "iniciar", "ticket": ticket,
              "tier": a.tier, "titulo": a.titulo, "fase": "CLASIFICACION",
              "desde": "IDLE", "commit": _commit(),
              "artefacto": a.artefacto or None,
              "contexto": a.contexto or None,
              # Se guarda con que reglas de ambiente se abrio el trabajo: sin esto,
              # cambiar el perfil a mitad de camino vuelve el historial ilegible,
              # porque no se puede saber bajo que regimen paso cada transicion.
              "ambiente_unico": perfil_mod.ambiente_unico(p)})

    print(f"  {ticket} [{a.tier}] — CLASIFICACION")
    if sistema == "interno":
        print(f"  ticket: {tickets_mod.ruta(RAIZ, ticket).relative_to(RAIZ)}")
    if a.contexto:
        print(f"  contexto previo: {a.contexto}")
    return 0


def cmd_estado(a) -> int:
    act = actual()
    if not act:
        print("\n  Sin trabajo registrado.\n")
        return 0
    print(f"\n  Ticket : {act.get('ticket')}")
    print(f"  Tier   : {act.get('tier')}")
    print(f"  Titulo : {act.get('titulo', '-')}")
    print(f"  Fase   : {act.get('fase')}")
    print(f"  Desde  : {act.get('ts')}")
    if act.get("motivo"):
        print(f"  Motivo : {act['motivo']}")

    reglas = cargar_reglas()
    tier = reglas.get("tiers", {}).get(act.get("tier"), {})
    salidas = [k for k in tier if k.startswith(f"{act.get('fase')}->")]
    if salidas:
        print("\n  Salidas posibles:")
        for s in salidas:
            g = tier[s].get("compuertas", [])
            print(f"    {s.split('->')[1]:<14} compuertas: {', '.join(g) or 'ninguna'}")
    print()
    return 0


def _norm_fase(nombre: str) -> str:
    """Los nodos del grafo son ASCII (DISENO, PUBLICACION) pero el texto de los
    docs usa eñes y tildes (DISEÑO, PUBLICACIÓN). Sin esto, copiar el nombre de
    fase desde la documentación a `mover --a` fallaba con 'transición no
    permitida' — encontrado auditando consistencia, no usando el comando."""
    tabla = str.maketrans("ÁÉÍÓÚÑáéíóúñ", "AEIOUNaeioun")
    return nombre.translate(tabla).strip().upper()


def cmd_mover(a) -> int:
    act = actual()
    if not act or act.get("fase") == "IDLE":
        print("No hay trabajo abierto. Empezá con `iniciar`.", file=sys.stderr)
        return 1

    reglas = cargar_reglas()
    desde, hacia, tier = act["fase"], _norm_fase(a.a), act["tier"]
    clave = f"{desde}->{hacia}"

    tabla = dict(reglas.get("comun", {}))
    tabla.update(reglas.get("tiers", {}).get(tier, {}))

    if clave not in tabla:
        posibles = [k for k in tabla if k.startswith(f"{desde}->")]
        print(f"Transicion no permitida para el tier {tier}: {clave}\n"
              f"Desde {desde} se puede ir a: "
              f"{', '.join(p.split('->')[1] for p in posibles) or 'ningun lado'}",
              file=sys.stderr)
        return 1

    declaradas = dict(x.split("=", 1) for x in (a.compuerta or []) if "=" in x)
    ok, fallos = verificar_compuertas(tabla[clave].get("compuertas", []), reglas,
                                      declaradas, act.get("ticket"))
    if not ok:
        print(f"\n  Transicion {clave} RECHAZADA:\n", file=sys.stderr)
        for f in fallos:
            print(f"    - {f}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    escribir({"ts": _ahora(), "evento": "mover", "ticket": act["ticket"],
              "tier": tier, "titulo": act.get("titulo"), "desde": desde,
              "fase": hacia, "compuertas": declaradas, "commit": _commit()})
    print(f"  {desde} -> {hacia}")
    return 0


def _salir(a, evento: str) -> int:
    act = actual()
    if not act or act.get("fase") == "IDLE":
        print("No hay trabajo abierto.", file=sys.stderr)
        return 1
    reglas = cargar_reglas()
    if act["fase"] in reglas.get("sin_abandono", []):
        print(f"De {act['fase']} no se sale con '{evento}': acá no queda nada por "
              f"decidir, solo pasos por terminar. Cerrá con `mover --a IDLE`.",
              file=sys.stderr)
        return 1
    escribir({"ts": _ahora(), "evento": evento, "ticket": act["ticket"],
              "tier": act["tier"], "titulo": act.get("titulo"),
              "desde": act["fase"], "fase": "IDLE", "motivo": a.motivo,
              "commit": _commit()})
    print(f"  {act['ticket']}: {evento} en {act['fase']} — {a.motivo}")
    return 0


def cmd_reanudar(a) -> int:
    """
    Reentra en la fase desde la que se pauso. No hay lista de fases reanudables:
    la prueba es la pausa misma.
    """
    log = leer_log()
    if not log:
        print("No hay historial.", file=sys.stderr)
        return 1
    ultima = log[-1]
    if ultima.get("evento") != "pausa":
        print(f"Lo ultimo registrado es '{ultima.get('evento')}', no una pausa. "
              f"Solo se reanuda lo que se pauso.", file=sys.stderr)
        return 1
    fase = ultima.get("desde")
    escribir({"ts": _ahora(), "evento": "reanudar", "ticket": ultima["ticket"],
              "tier": ultima["tier"], "titulo": ultima.get("titulo"),
              "desde": "IDLE", "fase": fase, "commit": _commit()})
    print(f"  {ultima['ticket']} reanudado en {fase}")
    if ultima.get("motivo"):
        print(f"  se habia pausado por: {ultima['motivo']}")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Maquina de estados de FAW")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("iniciar")
    # Opcional a proposito: con el registro interno, el identificador lo genera
    # FAW. Exigirlo obligaba a inventar uno a quien no usa ningun gestor.
    i.add_argument("--ticket", default="")
    i.add_argument("--tier", required=True)
    i.add_argument("--titulo", default="")
    # Tipo de artefacto: decide que skill oficial de la plataforma aplica. Sin
    # este dato el metodo no puede exigir la documentacion correcta, porque no
    # sabe cual es.
    i.add_argument("--artefacto", default="")
    # Documento de una consulta previa cuyo resultado ya cerro decisiones de
    # diseno. Evita volver a preguntar lo que el usuario ya contesto.
    i.add_argument("--contexto", default="")

    sub.add_parser("estado")
    sub.add_parser("reanudar")

    m = sub.add_parser("mover")
    m.add_argument("--a", required=True)
    m.add_argument("--compuerta", action="append", metavar="clave=valor")

    for nombre in ("pausar", "abandonar"):
        s = sub.add_parser(nombre)
        s.add_argument("--motivo", required=True)

    a = p.parse_args()
    return {
        "iniciar": cmd_iniciar, "estado": cmd_estado, "mover": cmd_mover,
        "reanudar": cmd_reanudar,
        "pausar": lambda x: _salir(x, "pausa"),
        "abandonar": lambda x: _salir(x, "abandono"),
    }[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
