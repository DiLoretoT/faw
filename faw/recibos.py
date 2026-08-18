"""
Recibos de compuerta.

El problema que resuelve: la primera version de FAW vendia cuatro compuertas
"de maquina" y solo una lo era. `estado.py` aceptaba que el agente escribiera
`--compuerta esquema="ok: ..."` sin haber corrido nada. Verificado ejecutandolo.

Ahora los verificadores, al pasar, emiten un recibo que registra QUE se
verifico, sobre QUE archivos (por hash) y en QUE commit. `estado.py` exige el
recibo y **recomputa los hashes**: si el contrato o el snapshot cambiaron
despues de emitirlo, el recibo esta vencido y la compuerta se cierra.

## Hasta donde llega esto, dicho sin adornos

Un recibo eleva el costo de falsear de "escribir un string" a "fabricar un JSON
con los hashes correctos, a proposito". Eso elimina el bypass accidental y
convierte al deliberado en un acto explicito y rastreable. **No lo hace
imposible**: sin un secreto que el agente no pueda leer, ningun archivo local es
infalsificable.

La irrevocabilidad real llega con el hook, que corre fuera de la conversacion.
Esto es el paso intermedio honesto, y se documenta como tal en vez de volver a
prometer lo que no da.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DIR_RECIBOS = Path(".faw") / "recibos"


def _ruta(compuerta: str, ambito: str | None = None) -> Path:
    """
    Un recibo por compuerta — o por (compuerta, ambito) cuando el verificador
    trabaja de a una unidad y el ticket abarca varias. El caso que motivo el
    ambito: `contrato` se verifica tabla por tabla, y con el archivo unico cada
    corrida pisaba a la anterior, asi que un ticket de 9 tablas cerraba DISENO
    probando solo la ultima.
    """
    if ambito:
        seguro = re.sub(r"[^A-Za-z0-9_.\-]", "_", ambito)
        return DIR_RECIBOS / f"{compuerta}.{seguro}.json"
    return DIR_RECIBOS / f"{compuerta}.json"


def _sha(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return "sha256:" + h.hexdigest()


def _commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except FileNotFoundError:
        return None


def emitir(compuerta: str, script: str, insumos: list[Path], detalle: str,
           ambito: str | None = None) -> Path:
    """Escribe el recibo de una compuerta que paso. Solo lo llaman los verificadores."""
    DIR_RECIBOS.mkdir(parents=True, exist_ok=True)
    recibo = {
        "compuerta": compuerta,
        "resultado": "PASA",
        "script": script,
        "emitido_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "insumos": {str(p).replace("\\", "/"): _sha(p) for p in insumos if p.exists()},
        "detalle": detalle,
    }
    if ambito:
        recibo["ambito"] = ambito
    destino = _ruta(compuerta, ambito)
    destino.write_text(json.dumps(recibo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  recibo: {destino}")
    return destino


def verificar(compuerta: str, exigir_commit_actual: bool = False,
              ambito: str | None = None) -> tuple[bool, str]:
    """
    Valida el recibo de una compuerta. Devuelve (paso, motivo).

    Recomputa el hash de cada insumo: si alguno cambio despues de emitirse el
    recibo, esta vencido. Es lo que evita perfilar una vez y despues cambiar el
    contrato sin volver a verificar.
    """
    ruta = _ruta(compuerta, ambito)
    if not ruta.exists():
        que = f"'{compuerta}'" + (f" para '{ambito}'" if ambito else "")
        return False, (f"no hay recibo de {que}. Corre el verificador "
                       f"y volve a intentar")

    try:
        r = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, f"el recibo '{ruta}' no es JSON valido"

    if r.get("resultado") != "PASA":
        return False, f"el recibo dice resultado='{r.get('resultado')}'"

    if ambito and r.get("ambito") != ambito:
        return False, (f"el recibo en '{ruta.name}' declara ambito "
                       f"'{r.get('ambito')}', no '{ambito}'")

    for archivo, hash_registrado in (r.get("insumos") or {}).items():
        p = Path(archivo)
        if not p.exists():
            return False, f"recibo vencido: el insumo '{archivo}' ya no existe"
        if _sha(p) != hash_registrado:
            return False, (f"recibo vencido: '{archivo}' cambio desde que se "
                           f"emitio. Volve a correr el verificador")

    if exigir_commit_actual:
        actual = _commit()
        if actual and r.get("commit") and r["commit"] != actual:
            return False, (f"recibo emitido en el commit {r['commit']} y HEAD "
                           f"esta en {actual}. Volve a verificar")

    detalle = r.get("detalle", "")
    return True, f"recibo de {r.get('emitido_en')} — {detalle}"


def invalidar(compuerta: str, ambito: str | None = None) -> None:
    """Borra el recibo. Lo llaman los verificadores cuando el resultado es FALLA."""
    ruta = _ruta(compuerta, ambito)
    if ruta.exists():
        ruta.unlink()
        print(f"  recibo invalidado: {ruta}")


def listar(compuerta: str) -> dict[str | None, Path]:
    """
    Recibos emitidos de una compuerta, por ambito. La clave None es el recibo
    legado sin ambito (formato previo a los recibos por tabla).

    El ambito se lee del contenido del recibo, no del nombre del archivo: el
    nombre sanitiza caracteres y no es reversible.
    """
    encontrados: dict[str | None, Path] = {}
    if not DIR_RECIBOS.is_dir():
        return encontrados
    legado = DIR_RECIBOS / f"{compuerta}.json"
    if legado.exists():
        encontrados[None] = legado
    for p in DIR_RECIBOS.glob(f"{compuerta}.*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if r.get("compuerta") == compuerta and r.get("ambito"):
            encontrados[r["ambito"]] = p
    return encontrados
